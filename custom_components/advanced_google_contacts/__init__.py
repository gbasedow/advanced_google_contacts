import logging
import voluptuous as vol

from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ConfigEntryAuthFailed
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util, slugify

from .calendar_sync import sync_events
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_CREATE_CONTACT_ENTITIES,
    CONF_TITLE_FORMAT_BIRTHDAY,
    CONF_TITLE_FORMAT_EVENT,
    DEFAULT_CREATE_CONTACT_ENTITIES,
    DEFAULT_TITLE_FORMAT_BIRTHDAY,
    DEFAULT_TITLE_FORMAT_EVENT,
    EVENT_TYPE_BIRTHDAY,
    LEGACY_DOMAIN,
    SERVICE_SYNC_BIRTHDAYS,
    SERVICE_SYNC_EVENTS,
)
from .coordinator import Coordinator
from .title_format import TitleFormatError, validate_title_format

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ISSUE_LEGACY = "legacy_integration_installed"


def _title_format(value):
    try:
        return validate_title_format(value)
    except TitleFormatError as err:
        raise vol.Invalid(f"Ungültiges Titelformat: {err}") from err


_BASE = {
    vol.Required("calendar"): cv.entity_id,
    vol.Required("months"): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
}
SCHEMA = vol.Schema(_BASE)
EVENTS_SCHEMA = vol.Schema({
    **_BASE,
    vol.Optional("event_types", default=[EVENT_TYPE_BIRTHDAY]): vol.All(
        cv.ensure_list, [vol.All(cv.string, vol.Length(min=1))], vol.Length(min=1)
    ),
    vol.Optional("title_format"): _title_format,
})


def sync_issue_id(calendar_entity_id: str) -> str:
    return f"sync_failed_{slugify(calendar_entity_id)}"


def _formats(entry, override=None) -> dict[str, str]:
    if override:
        return {EVENT_TYPE_BIRTHDAY: override, "event": override}
    return {
        EVENT_TYPE_BIRTHDAY: entry.options.get(CONF_TITLE_FORMAT_BIRTHDAY, DEFAULT_TITLE_FORMAT_BIRTHDAY),
        "event": entry.options.get(CONF_TITLE_FORMAT_EVENT, DEFAULT_TITLE_FORMAT_EVENT),
    }


async def _run_sync(hass, call, event_types):
    cal = call.data["calendar"]
    if not cal.startswith("calendar."):
        raise HomeAssistantError("calendar muss eine calendar.* Entität sein.")
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise HomeAssistantError("Advanced Google Contacts ist nicht geladen.")
    coordinator = next(iter(entries.values()))
    formats = _formats(coordinator.entry, call.data.get("title_format"))
    info = {
        "time": dt_util.utcnow().isoformat(),
        "calendar": cal,
        "months": call.data["months"],
        "event_types": sorted(event_types),
        "title_formats": formats,
    }
    issue_id = sync_issue_id(cal)
    try:
        result = await sync_events(hass, coordinator, cal, call.data["months"], event_types, formats)
    except HomeAssistantError as err:
        coordinator.last_sync = {**info, "success": False, "error": str(err)}
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="sync_failed",
            translation_placeholders={"calendar": cal, "error": str(err)},
        )
        raise
    coordinator.last_sync = {**info, "success": True, "result": result}
    ir.async_delete_issue(hass, DOMAIN, issue_id)
    return result


def _check_legacy_integration(hass) -> None:
    """Raise a repair issue while the old google_contacts_basedog entry exists."""
    if hass.config_entries.async_entries(LEGACY_DOMAIN):
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_LEGACY,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_LEGACY,
            translation_placeholders={"legacy_domain": LEGACY_DOMAIN, "domain": DOMAIN},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_LEGACY)


def _remove_contact_registry_entries(hass, entry):
    """Remove every entity/device owned by this integration's config entry.

    Called only when contact entities are disabled. The coordinator and birthday
    sync remain loaded; only registry objects created for contacts are removed.
    """
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Remove entities explicitly first. This also covers any historical entity
    # that might no longer be linked to a device.
    entity_ids = [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    ]
    for entity_id in entity_ids:
        entity_registry.async_remove(entity_id)

    device_ids = [
        device.id
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    ]
    for device_id in device_ids:
        device_registry.async_remove_device(device_id)

    if entity_ids or device_ids:
        _LOGGER.info(
            "Removed %d contact entities and %d contact devices because contact loading is disabled",
            len(entity_ids),
            len(device_ids),
        )


async def async_setup(hass, config):
    async def sync_birthdays_action(call):
        return await _run_sync(hass, call, [EVENT_TYPE_BIRTHDAY])

    async def sync_events_action(call):
        return await _run_sync(hass, call, call.data["event_types"])

    for name, handler, schema in (
        (SERVICE_SYNC_BIRTHDAYS, sync_birthdays_action, SCHEMA),
        (SERVICE_SYNC_EVENTS, sync_events_action, EVENTS_SCHEMA),
    ):
        if not hass.services.has_service(DOMAIN, name):
            hass.services.async_register(
                DOMAIN, name, handler, schema=schema, supports_response=SupportsResponse.OPTIONAL
            )
    return True


async def async_setup_entry(hass, entry):
    impl = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )
    oauth = config_entry_oauth2_flow.OAuth2Session(hass, entry, impl)
    create_entities = entry.options.get(
        CONF_CREATE_CONTACT_ENTITIES, DEFAULT_CREATE_CONTACT_ENTITIES
    )
    # Without contact entities nobody needs periodic polling: the birthday sync
    # fetches fresh contacts itself.
    coordinator = Coordinator(hass, entry, oauth, poll=create_entities)
    await coordinator.async_config_entry_first_refresh()

    # Resolve the account identity before exposing entities. If the existing OAuth
    # grant predates the OpenID scopes, Google UserInfo returns 401/403. Raising
    # ConfigEntryAuthFailed from async_setup_entry makes Home Assistant start the
    # integration's linked reauthentication flow automatically.
    try:
        account_email = await coordinator.async_account_email()
    except Exception as err:
        status = getattr(err, "status", None)
        if status in (401, 403):
            raise ConfigEntryAuthFailed(
                "Google authorization must be renewed to grant the account identity scopes"
            ) from err
        raise

    if entry.title != account_email:
        hass.config_entries.async_update_entry(entry, title=account_email)
    _LOGGER.info("Authenticated Google Contacts account: %s", account_email)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    _check_legacy_integration(hass)
    loaded_platforms = hass.data.setdefault(f"{DOMAIN}_loaded_platforms", set())

    if create_entities:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        loaded_platforms.add(entry.entry_id)
    else:
        loaded_platforms.discard(entry.entry_id)
        # Important for transitions from enabled -> disabled and also makes
        # cleanup self-healing after a restart if stale registry entries remain.
        _remove_contact_registry_entries(hass, entry)

    return True


async def async_unload_entry(hass, entry):
    """Unload only platforms that were actually loaded for this entry."""
    loaded_platforms = hass.data.get(f"{DOMAIN}_loaded_platforms", set())

    if entry.entry_id in loaded_platforms:
        ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        if not ok:
            return False
        loaded_platforms.discard(entry.entry_id)

    # If contact entities were disabled by the options change, remove their
    # registry records after a successfully unloaded sensor platform.
    if not entry.options.get(
        CONF_CREATE_CONTACT_ENTITIES, DEFAULT_CREATE_CONTACT_ENTITIES
    ):
        _remove_contact_registry_entries(hass, entry)

    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
