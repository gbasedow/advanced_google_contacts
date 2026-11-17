"""Diagnostics download and repair issues with a real setup."""
from __future__ import annotations

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry

from custom_components.advanced_google_contacts import sync_issue_id
from custom_components.advanced_google_contacts.const import DOMAIN
from .conftest import EMAIL, person, sync


async def test_diagnostics_contains_no_secrets(hass, hass_client, setup_integration, local_calendar):
    assert await __import__("homeassistant.setup").setup.async_setup_component(hass, "diagnostics", {})
    entry = await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10), events=[("Hochzeitstag", (2010, 1, 1))])],
                                    create_contact_entities=False)
    await sync(hass)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    text = repr(diag)
    for secret in ("ACCESS-SECRET", "REFRESH-SECRET", EMAIL, "Anna", "Muster", "Hochzeitstag"):
        assert secret not in text, secret
    assert diag["contacts"]["total"] == 1
    assert diag["contacts"]["events_by_type"] == {"custom": 1}
    assert diag["last_sync"]["success"] is True


async def test_sync_failure_issue_lifecycle(hass, setup_integration, google, local_calendar):
    await setup_integration([person("1", "A B", birthday=(1990, 3, 10))], create_contact_entities=False)
    reg = ir.async_get(hass)
    google.people_status = 500
    google.install()
    with pytest.raises(HomeAssistantError):
        await sync(hass)
    assert reg.async_get_issue(DOMAIN, sync_issue_id(local_calendar))
    google.people_status = 200
    google.install()
    await sync(hass)
    assert reg.async_get_issue(DOMAIN, sync_issue_id(local_calendar)) is None


async def test_invalid_calendar_issue(hass, setup_integration, local_calendar):
    await setup_integration([person("1", "A B", birthday=(1990, 3, 10))], create_contact_entities=False)
    with pytest.raises(HomeAssistantError):
        await sync(hass, calendar="calendar.gibt_es_nicht")
    assert ir.async_get(hass).async_get_issue(DOMAIN, sync_issue_id("calendar.gibt_es_nicht"))


async def test_issues_removed_with_integration(hass, setup_integration, google, local_calendar):
    """Expected: removing the integration also removes its repair issues."""
    entry = await setup_integration([person("1", "A B", birthday=(1990, 3, 10))], create_contact_entities=False)
    google.people_status = 500
    google.install()
    with pytest.raises(HomeAssistantError):
        await sync(hass)
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, sync_issue_id(local_calendar)) is None


async def test_legacy_issue_on_setup(hass, setup_integration):
    MockConfigEntry(domain="google_contacts_basedog").add_to_hass(hass)
    await setup_integration([person("1", "A B")], create_contact_entities=False)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "legacy_integration_installed")


async def test_issue_translations_have_placeholders(hass):
    """Every placeholder used in a translation is provided by the code."""
    import json, pathlib, re
    base = pathlib.Path(__file__).parents[1] / "custom_components" / DOMAIN
    for lang in ("strings.json", "translations/de.json", "translations/en.json"):
        data = json.loads((base / lang).read_text())
        used = set(re.findall(r"\{(\w+)\}", json.dumps(data["issues"])))
        assert used <= {"calendar", "error", "legacy_domain", "domain"}, (lang, used)
