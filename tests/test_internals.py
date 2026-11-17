import datetime as dt
from types import SimpleNamespace

import pytest
import voluptuous as vol
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.advanced_google_contacts import (
    EVENTS_SCHEMA, _remove_contact_registry_entries, _run_sync, _check_legacy_integration, sync_issue_id,
)
from custom_components.advanced_google_contacts.calendar_sync import MARKER
from custom_components.advanced_google_contacts.const import DOMAIN
from custom_components.advanced_google_contacts.coordinator import Coordinator
from custom_components.advanced_google_contacts.diagnostics import async_get_config_entry_diagnostics
from .fakes import FakeCal, FakeCoord, contact, setup_cal


def make_local_entry(hass, **options):
    entry = MockConfigEntry(domain=DOMAIN, title="someone@example.com", options=options,
                            data={"auth_implementation": "x", "token": {"access_token": "SECRET", "refresh_token": "SECRET2"}})
    entry.add_to_hass(hass)
    return entry


async def test_service_creates_and_clears_repair_issue(hass):
    entry = make_local_entry(hass)
    cal = FakeCal(); setup_cal(hass, cal)
    coord = FakeCoord({"1": contact("Anna Muster", (1990, 3, 10))}, entry=entry)
    hass.data[DOMAIN] = {entry.entry_id: coord}
    call = SimpleNamespace(data={"calendar": "calendar.geb", "months": 12})
    reg = ir.async_get(hass)

    cal.keep_description = False
    with pytest.raises(HomeAssistantError):
        await _run_sync(hass, call, ["birthday"])
    issue = reg.async_get_issue(DOMAIN, sync_issue_id("calendar.geb"))
    assert issue and issue.translation_key == "sync_failed" and issue.severity == ir.IssueSeverity.ERROR
    assert coord.last_sync["success"] is False

    cal.keep_description = True
    cal.events.clear()
    res = await _run_sync(hass, call, ["birthday"])
    assert res["created"] == 1
    assert reg.async_get_issue(DOMAIN, sync_issue_id("calendar.geb")) is None
    assert coord.last_sync["success"] is True

    # Diagnostics: no token, no account, no contact names (the error names one).
    cal.keep_description = False
    cal.events.clear()
    with pytest.raises(HomeAssistantError):
        await _run_sync(hass, call, ["birthday"])
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = repr(diag)
    assert "SECRET" not in text and "someone@example.com" not in text and "Anna Muster" not in text
    assert diag["contacts"]["total"] == 1 and diag["contacts"]["with_birthday_year"] == 1
    assert diag["repair_issues"] == [sync_issue_id("calendar.geb")]
    assert diag["last_sync"]["success"] is False and "**REDACTED**" in diag["last_sync"]["error"]


async def test_title_format_option_used(hass):
    entry = make_local_entry(hass, title_format_birthday="🎂 {name}")
    cal = FakeCal(); setup_cal(hass, cal)
    hass.data[DOMAIN] = {entry.entry_id: FakeCoord({"1": contact("Anna", (1990, 3, 10))}, entry=entry)}
    await _run_sync(hass, SimpleNamespace(data={"calendar": "calendar.geb", "months": 12}), ["birthday"])
    assert cal.summaries() == [("🎂 Anna", MARKER)]
    # Per-call override wins.
    await _run_sync(hass, SimpleNamespace(data={"calendar": "calendar.geb", "months": 12, "title_format": "B {name}"}), ["birthday"])
    assert cal.summaries() == [("B Anna", MARKER)]


def test_events_schema():
    data = EVENTS_SCHEMA({"calendar": "calendar.x", "months": "3"})
    assert data["event_types"] == ["birthday"] and data["months"] == 3
    assert EVENTS_SCHEMA({"calendar": "calendar.x", "months": 3, "event_types": "anniversary"})["event_types"] == ["anniversary"]
    with pytest.raises(vol.Invalid):
        EVENTS_SCHEMA({"calendar": "calendar.x", "months": 3, "title_format": "{age}"})
    with pytest.raises(vol.Invalid):
        EVENTS_SCHEMA({"calendar": "calendar.x", "months": 3, "event_types": []})


async def test_legacy_issue(hass):
    reg = ir.async_get(hass)
    MockConfigEntry(domain="google_contacts_basedog").add_to_hass(hass)
    _check_legacy_integration(hass)
    assert reg.async_get_issue(DOMAIN, "legacy_integration_installed")
    for e in hass.config_entries.async_entries("google_contacts_basedog"):
        await hass.config_entries.async_remove(e.entry_id)
    _check_legacy_integration(hass)
    assert reg.async_get_issue(DOMAIN, "legacy_integration_installed") is None


async def test_options_flow(hass):
    entry = make_local_entry(hass, create_contact_entities=False)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["description_placeholders"]["name"] == "{name}"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        "create_contact_entities": False, "title_format_birthday": "{age}", "title_format_event": "{type} {name}"})
    assert result["type"] == FlowResultType.FORM and result["errors"] == {"title_format_birthday": "invalid_title_format"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        "create_contact_entities": False, "title_format_birthday": " 🎂 {name} ", "title_format_event": "{type} {name}"})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["title_format_birthday"] == "🎂 {name}"


async def test_registry_cleanup(hass):
    entry = make_local_entry(hass)
    other = MockConfigEntry(domain="other"); other.add_to_hass(hass)
    devreg, entreg = dr.async_get(hass), er.async_get(hass)
    dv = devreg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, "p1")})
    entreg.async_get_or_create("sensor", DOMAIN, "u1", config_entry=entry, device_id=dv.id)
    d2 = devreg.async_get_or_create(config_entry_id=other.entry_id, identifiers={("other", "x")})
    entreg.async_get_or_create("sensor", "other", "u2", config_entry=other, device_id=d2.id)
    _remove_contact_registry_entries(hass, entry)
    assert not er.async_entries_for_config_entry(entreg, entry.entry_id)
    assert not dr.async_entries_for_config_entry(devreg, entry.entry_id)
    assert er.async_entries_for_config_entry(entreg, other.entry_id)


async def test_coordinator_poll_flag(hass):
    entry = make_local_entry(hass)
    assert Coordinator(hass, entry, None, poll=False).update_interval is None
    assert Coordinator(hass, entry, None, poll=True).update_interval == dt.timedelta(minutes=30)
