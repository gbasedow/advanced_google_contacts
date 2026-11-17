import logging
import voluptuous as vol

from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ConfigEntryAuthFailed
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .birthday_sync import sync_birthdays
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_CREATE_CONTACT_ENTITIES,
    DEFAULT_CREATE_CONTACT_ENTITIES,
)
from .coordinator import Coordinator

_LOGGER = logging.getLogger(__name__)

SCHEMA = vol.Schema({
    vol.Required("calendar"): cv.entity_id,
    vol.Required("months"): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
})


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
        for entity in entity_registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    ]
    for entity_id in entity_ids:
        entity_registry.async_remove(entity_id)

    # HA Core 2026.8+ devices belong to exactly one config entry.
    device_ids = [
        device.id
        for device in device_registry.devices.values()
        if device.config_entry_id == entry.entry_id
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
    async def action(call):
        cal = call.data["calendar"]
        if not cal.startswith("calendar."):
            raise HomeAssistantError("calendar muss eine calendar.* Entität sein.")
        entries = hass.data.get(DOMAIN, {})
        if not entries:
            raise HomeAssistantError("Google Contacts Basedog ist nicht geladen.")
        return await sync_birthdays(
            hass, next(iter(entries.values())), cal, call.data["months"]
        )

    if not hass.services.has_service(DOMAIN, "sync_birthdays_from_google_contacts"):
        hass.services.async_register(
            DOMAIN,
            "sync_birthdays_from_google_contacts",
            action,
            schema=SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
    return True


async def async_setup_entry(hass, entry):
    impl = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )
    oauth = config_entry_oauth2_flow.OAuth2Session(hass, entry, impl)
    coordinator = Coordinator(hass, entry, oauth)
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
    loaded_platforms = hass.data.setdefault(f"{DOMAIN}_loaded_platforms", set())

    create_entities = entry.options.get(
        CONF_CREATE_CONTACT_ENTITIES, DEFAULT_CREATE_CONTACT_ENTITIES
    )
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
