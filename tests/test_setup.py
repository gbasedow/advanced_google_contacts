"""Lifecycle: setup, polling, options, reload, unload, auth and network errors."""
from __future__ import annotations

from datetime import timedelta

import pytest
from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntryState, SOURCE_REAUTH
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.advanced_google_contacts.const import DOMAIN
from .conftest import EMAIL, person

PEOPLE = [
    person("1", "Anna Muster", birthday=(1990, 3, 10), phoneNumbers=[{"value": "+49 1"}]),
    person("2", "Bernd Beispiel", birthday=(None, 12, 24)),
]


async def test_setup_entities_on_creates_devices_and_sensors(hass, setup_integration):
    entry = await setup_integration(PEOPLE, create_contact_entities=True)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.title == EMAIL
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert sorted(d.name for d in devices) == ["Anna Muster", "Bernd Beispiel"]
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    # Anna: names, phoneNumbers, birthdays; Bernd: names, birthdays
    assert len(entities) == 5


async def test_default_option_creates_entities(hass, setup_integration):
    """Without stored options the code default (entities on) applies."""
    entry = await setup_integration(PEOPLE)
    assert er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


async def test_setup_entities_off_no_entities_no_polling(hass, setup_integration, google):
    entry = await setup_integration(PEOPLE, create_contact_entities=False)
    assert entry.state is ConfigEntryState.LOADED
    assert not er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    calls = google.people_calls()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=3))
    await hass.async_block_till_done()
    assert google.people_calls() == calls


async def test_polling_every_30_minutes_with_entities(hass, setup_integration, google):
    await setup_integration(PEOPLE, create_contact_entities=True)
    calls = google.people_calls()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=31))
    await hass.async_block_till_done()
    assert google.people_calls() == calls + 1


async def test_pagination_reads_all_pages(hass, setup_integration, google):
    google.page_size = 2
    people = [person(str(i), f"P{i} X", birthday=(1990, 1, i + 1)) for i in range(5)]
    entry = await setup_integration(people, create_contact_entities=False)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert len(coordinator.data) == 5
    assert google.people_calls() == 3


async def test_deleted_and_nameless_contacts(hass, setup_integration):
    people = [person("1", "Gone", deleted=True), person("2", None, birthday=(2000, 1, 1)), {"names": []}]
    entry = await setup_integration(people, create_contact_entities=False)
    data = hass.data[DOMAIN][entry.entry_id].data
    assert list(data) == ["people/2"]
    assert data["people/2"]["display_name"] == "Unbenannter Kontakt"


async def test_options_on_off_on(hass, setup_integration):
    entry = await setup_integration(PEOPLE, create_contact_entities=True)
    entreg, devreg = er.async_get(hass), dr.async_get(hass)
    assert er.async_entries_for_config_entry(entreg, entry.entry_id)

    hass.config_entries.async_update_entry(entry, options={**entry.options, "create_contact_entities": False})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert not er.async_entries_for_config_entry(entreg, entry.entry_id)
    assert not dr.async_entries_for_config_entry(devreg, entry.entry_id)

    hass.config_entries.async_update_entry(entry, options={**entry.options, "create_contact_entities": True})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert len(er.async_entries_for_config_entry(entreg, entry.entry_id)) == 5


async def test_unload_and_remove(hass, setup_integration):
    entry = await setup_integration(PEOPLE, create_contact_entities=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()


async def test_people_401_starts_reauth(hass, setup_integration, google):
    google.people_status = 401
    entry = await setup_integration(PEOPLE)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == SOURCE_REAUTH for f in flows)


async def test_userinfo_403_starts_reauth(hass, setup_integration, google):
    google.userinfo_status = 403
    entry = await setup_integration(PEOPLE)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["context"]["source"] == SOURCE_REAUTH for f in hass.config_entries.flow.async_progress())


async def test_people_500_retries_setup(hass, setup_integration, google):
    google.people_status = 500
    entry = await setup_integration(PEOPLE)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_people_network_error_retries_setup(hass, setup_integration, google):
    google.people_exc = ClientError("offline")
    entry = await setup_integration(PEOPLE)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_people_timeout_retries_setup(hass, setup_integration, google):
    google.people_exc = TimeoutError()
    entry = await setup_integration(PEOPLE)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("exc", [ClientError("offline"), TimeoutError()])
async def test_userinfo_network_error_should_retry_setup(hass, setup_integration, google, exc):
    """Expected: a temporary network error on UserInfo leads to a retry, not a permanent setup error."""
    google.userinfo_exc = exc
    entry = await setup_integration(PEOPLE)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_userinfo_500_should_retry_setup(hass, setup_integration, google):
    google.userinfo_status = 500
    entry = await setup_integration(PEOPLE)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_userinfo_without_email_starts_reauth(hass, setup_integration, google):
    google.email = None
    entry = await setup_integration(PEOPLE)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["context"]["source"] == SOURCE_REAUTH for f in hass.config_entries.flow.async_progress())


async def test_legacy_entry_gets_unique_id(hass, setup_integration):
    """Entries from before 0.4.0 have no unique_id; setup binds them to the account."""
    entry = await setup_integration(PEOPLE, create_contact_entities=False)
    assert entry.unique_id == EMAIL


async def test_userinfo_retry_recovers(hass, setup_integration, google):
    google.userinfo_status = 500
    entry = await setup_integration(PEOPLE)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    google.userinfo_status = 200
    google.install()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED


async def test_service_without_loaded_entry(hass, setup_integration, google, local_calendar):
    from homeassistant.exceptions import HomeAssistantError
    from .conftest import sync
    google.people_status = 500
    await setup_integration(PEOPLE)
    with pytest.raises(HomeAssistantError, match="nicht geladen"):
        await sync(hass)
