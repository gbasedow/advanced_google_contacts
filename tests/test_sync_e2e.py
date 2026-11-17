"""Calendar sync end to end through the HA action against a real local_calendar."""
from __future__ import annotations

import asyncio

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.advanced_google_contacts.calendar_sync import MARKER
from .conftest import add_calendar_event, calendar_events, person, sync

LEGACY = "Synchronisiert aus Google Contacts Basedog"
# Frozen "now": 2026-11-17 (Europe/Berlin)


async def test_birthdays_created_idempotent(hass, setup_integration, local_calendar):
    await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10)),
                             person("2", "Bernd B", birthday=(None, 12, 24))], create_contact_entities=False)
    res = await sync(hass, "sync_birthdays_from_google_contacts", months=12)
    assert res == {"desired": 2, "created": 2, "deleted": 0, "unchanged": 0}
    assert await calendar_events(hass, local_calendar) == [
        ("2026-12-24", "Geburtstag Bernd B", MARKER),
        ("2027-03-10", "Geburtstag Anna Muster - 37", MARKER),
    ]
    assert (await sync(hass, "sync_birthdays_from_google_contacts"))["created"] == 0


async def test_today_and_range_end_included(hass, setup_integration, local_calendar):
    await setup_integration([person("1", "Heute X", birthday=(2000, 11, 17)),
                             person("2", "Ende X", birthday=(2000, 12, 17)),
                             person("3", "Danach X", birthday=(2000, 12, 18))], create_contact_entities=False)
    await sync(hass, months=1)
    titles = [t for _d, t, _x in await calendar_events(hass, local_calendar)]
    assert titles == ["Geburtstag Heute X - 26", "Geburtstag Ende X - 26"]


async def test_legacy_entries_kept(hass, setup_integration, local_calendar):
    await add_calendar_event(hass, local_calendar, "Geburtstag Anna Muster - 37", "2027-03-10", LEGACY)
    await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10))], create_contact_entities=False)
    assert (await sync(hass))["unchanged"] == 1
    assert len(await calendar_events(hass, local_calendar)) == 1


async def test_manual_entries_untouched(hass, setup_integration, local_calendar):
    await add_calendar_event(hass, local_calendar, "Geburtstag Fremd", "2027-01-01")
    await add_calendar_event(hass, local_calendar, "Zahnarzt", "2027-01-02", "Synchronisiert aus Advanced Google Contacts?")
    await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10))], create_contact_entities=False)
    await sync(hass)
    summaries = [t for _d, t, _x in await calendar_events(hass, local_calendar)]
    assert "Geburtstag Fremd" in summaries and "Zahnarzt" in summaries


async def test_contact_deleted_and_renamed(hass, setup_integration, google, local_calendar):
    await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10)),
                             person("2", "Bernd B", birthday=(1980, 1, 5))], create_contact_entities=False)
    await sync(hass)
    google.people = [person("1", "Anna Neu", birthday=(1990, 3, 10))]
    google.install()
    res = await sync(hass)
    assert res == {"desired": 1, "created": 1, "deleted": 2, "unchanged": 0}
    assert [t for _d, t, _x in await calendar_events(hass, local_calendar)] == ["Geburtstag Anna Neu - 37"]


async def test_event_types_scopes(hass, setup_integration, local_calendar):
    await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10), events=[
        ("anniversary", (2015, 6, 1)), ("Hochzeitstag", (2012, 7, 2)), ("other", (None, 8, 3))])],
        create_contact_entities=False)
    res = await sync(hass, event_types=["birthday", "anniversary", "custom", "other"])
    assert res["created"] == 4
    assert [t for _d, t, _x in await calendar_events(hass, local_calendar)] == [
        "Geburtstag Anna Muster - 37", "Jahrestag Anna Muster - 12", "Hochzeitstag Anna Muster - 15", "Ereignis Anna Muster"]
    # Birthday-only and single-label calls leave the other types alone.
    assert (await sync(hass, "sync_birthdays_from_google_contacts"))["deleted"] == 0
    assert (await sync(hass, event_types=["Hochzeitstag"]))["deleted"] == 0
    assert len(await calendar_events(hass, local_calendar)) == 4


async def test_unknown_or_miscased_type_is_rejected(hass, setup_integration, local_calendar):
    """Expected: a typo like 'Birthday' or 'anniversaries' is reported instead of silently syncing nothing."""
    await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10))], create_contact_entities=False)
    with pytest.raises((HomeAssistantError, vol.Invalid)):
        await sync(hass, event_types=["Birthday"])


async def test_title_format_option_and_override(hass, setup_integration, local_calendar):
    entry = await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10))],
                                    create_contact_entities=False, title_format_birthday="🎂 {first_name}[ ({age})]")
    await sync(hass)
    assert [t for _d, t, _x in await calendar_events(hass, local_calendar)] == ["🎂 Anna (37)"]
    await sync(hass, title_format="{last_name}, {first_name}")
    assert [t for _d, t, _x in await calendar_events(hass, local_calendar)] == ["Muster, Anna"]


@pytest.mark.parametrize("data", [
    {"months": 0}, {"months": 121}, {"calendar": "light.x"}, {"event_types": []},
    {"title_format": "{age}"}, {"title_format": "{name"},
])
async def test_invalid_service_data(hass, setup_integration, local_calendar, data):
    await setup_integration([person("1", "A B", birthday=(1990, 3, 10))], create_contact_entities=False)
    with pytest.raises((vol.Invalid, HomeAssistantError, ServiceValidationError)):
        await sync(hass, **data)


async def test_missing_calendar_entity(hass, setup_integration, local_calendar):
    await setup_integration([person("1", "A B", birthday=(1990, 3, 10))], create_contact_entities=False)
    with pytest.raises(HomeAssistantError, match="keine verfügbare"):
        await sync(hass, calendar="calendar.gibt_es_nicht")


async def test_duplicate_names_same_day(hass, setup_integration, local_calendar):
    await setup_integration([person("1", "Max Mustermann", birthday=(1990, 3, 10)),
                             person("2", "Max Mustermann", birthday=(1990, 3, 10)),
                             person("3", "Max Mustermann", birthday=(1985, 3, 10))], create_contact_entities=False)
    res = await sync(hass)
    assert res["desired"] == 2  # same title collapses, different age differs


async def test_names_with_special_characters(hass, setup_integration, local_calendar):
    names = ["Ä Ö Ü ß", "A {b} [c]", "😀 Emoji", "Zeile\nUmbruch", "  Leer  "]
    await setup_integration([person(str(i), n, birthday=(1990, 3, 10 + i)) for i, n in enumerate(names)],
                            create_contact_entities=False)
    res = await sync(hass)
    assert res["created"] == 5
    assert (await sync(hass))["unchanged"] == 5


async def test_birthday_without_date_parts(hass, setup_integration, local_calendar):
    p = person("1", "Nur Text")
    p["birthdays"] = [{"text": "irgendwann"}, {"date": {"year": 1990}}, {"date": {"month": 2, "day": 30}}, {"date": None}]
    await setup_integration([p, person("2", "Ok X", birthday=(1990, 3, 10))], create_contact_entities=False)
    assert (await sync(hass))["desired"] == 1


async def test_feb_29_in_non_leap_years(hass, setup_integration, local_calendar):
    await setup_integration([person("1", "Schalt Jahr", birthday=(2000, 2, 29))], create_contact_entities=False)
    await sync(hass, months=40)  # 2027, 2028 (leap), 2029, 2030
    assert [d for d, _t, _x in await calendar_events(hass, local_calendar, end="2031-01-01")] == [
        "2027-02-28", "2028-02-29", "2029-02-28", "2030-02-28"]


async def test_birth_year_in_future_or_today(hass, setup_integration, local_calendar):
    await setup_integration([person("1", "Zukunft X", birthday=(2027, 5, 1)),
                             person("2", "Heute Y", birthday=(2026, 11, 17))], create_contact_entities=False)
    await sync(hass, months=24)
    titles = [t for _d, t, _x in await calendar_events(hass, local_calendar, end="2029-01-01")]
    assert "Geburtstag Zukunft X - 1" in titles and "Geburtstag Heute Y - 0" in titles


async def test_concurrent_syncs_same_calendar(hass, setup_integration, local_calendar):
    """Expected: two parallel calls (e.g. two automations) end without error and without duplicates."""
    await setup_integration([person(str(i), f"P{i} X", birthday=(1990, 1 + i % 12, 1 + i % 28)) for i in range(20)],
                            create_contact_entities=False)
    results = await asyncio.gather(sync(hass), sync(hass), return_exceptions=True)
    assert not [r for r in results if isinstance(r, Exception)], results
    assert len(await calendar_events(hass, local_calendar)) == 20


async def test_people_api_error_during_sync_leaves_calendar(hass, setup_integration, google, local_calendar):
    await setup_integration([person("1", "A B", birthday=(1990, 3, 10))], create_contact_entities=False)
    await sync(hass)
    before = await calendar_events(hass, local_calendar)
    google.people_status = 500
    google.install()
    with pytest.raises(HomeAssistantError):
        await sync(hass)
    assert await calendar_events(hass, local_calendar) == before


async def test_reauth_on_401_during_sync(hass, setup_integration, google, local_calendar):
    from homeassistant.config_entries import SOURCE_REAUTH
    await setup_integration([person("1", "A B", birthday=(1990, 3, 10))], create_contact_entities=False)
    google.people_status = 401
    google.install()
    with pytest.raises(HomeAssistantError, match="Anmeldung"):
        await sync(hass)
    await hass.async_block_till_done()
    assert any(f["context"]["source"] == SOURCE_REAUTH for f in hass.config_entries.flow.async_progress())


async def test_large_contact_list(hass, setup_integration, local_calendar):
    people = [person(str(i), f"Person {i:04d}", birthday=(1950 + i % 50, 1 + i % 12, 1 + i % 28)) for i in range(500)]
    await setup_integration(people, create_contact_entities=False)
    res = await sync(hass, months=24)
    assert res["created"] == 1000
    assert (await sync(hass, months=24))["unchanged"] == 1000


async def test_sync_updates_entities(hass, setup_integration, google, local_calendar):
    """A sync fetches fresh data; with entities on, sensors pick it up."""
    from homeassistant.helpers import entity_registry as er
    entry = await setup_integration([person("1", "A B", phoneNumbers=[{"value": "1"}])], create_contact_entities=True)
    google.people = [person("1", "A B", phoneNumbers=[{"value": "2"}], birthday=(1990, 3, 10))]
    google.install()
    await sync(hass)
    await hass.async_block_till_done()
    ent = next(e for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) if e.original_name == "Telefon")
    assert hass.states.get(ent.entity_id).state == "2"


async def test_month_end_range(hass, setup_integration, local_calendar, freezer):
    freezer.move_to("2027-01-31 12:00:00+01:00")
    await setup_integration([person("1", "Feb X", birthday=(2000, 2, 28)), person("2", "Mar X", birthday=(2000, 3, 1))],
                            create_contact_entities=False)
    await sync(hass, months=1)  # 2027-01-31 + 1 month = 2027-02-28
    assert [t for _d, t, _x in await calendar_events(hass, local_calendar, start="2027-01-01")] == ["Geburtstag Feb X - 27"]


async def test_timezone_far_east(hass, setup_integration, local_calendar, freezer):
    """Late evening UTC is already the next day in Kiritimati; 'today' must follow HA's time zone."""
    await hass.config.async_set_time_zone("Pacific/Kiritimati")
    freezer.move_to("2026-11-16 23:00:00+00:00")  # 2026-11-17 13:00 local
    await setup_integration([person("1", "Heute X", birthday=(2000, 11, 17))], create_contact_entities=False)
    await sync(hass, months=1)
    assert [d for d, _t, _x in await calendar_events(hass, local_calendar)] == ["2026-11-17"]
