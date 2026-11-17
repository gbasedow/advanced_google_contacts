"""Sync logic against special calendars and changed parameters."""
from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pytest
from homeassistant.components.calendar import DATA_COMPONENT, CalendarEntity, CalendarEntityFeature, CalendarEvent
from homeassistant.exceptions import HomeAssistantError

from custom_components.advanced_google_contacts.calendar_sync import MARKER
from .conftest import calendar_events, person, sync


class CreateOnlyCal(CalendarEntity):
    """A calendar that can create but not delete (e.g. some CalDAV setups)."""
    _attr_supported_features = CalendarEntityFeature.CREATE_EVENT

    def __init__(self):
        self.events = []

    @property
    def event(self):
        return None

    async def async_get_events(self, hass, start, end):
        return [e for e in self.events if start.date() <= e.start < end.date()]

    async def async_create_event(self, **kw):
        self.events.append(CalendarEvent(start=kw["dtstart"], end=kw["dtend"], summary=kw["summary"],
                                         description=kw.get("description"), uid=str(len(self.events))))


async def test_calendar_without_delete_should_not_create_duplicates(hass, setup_integration, google):
    """Expected: when stale entries cannot be deleted, the sync fails BEFORE creating replacements."""
    await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10))], create_contact_entities=False)
    cal = CreateOnlyCal()
    comp = MagicMock(); comp.get_entity.return_value = cal
    hass.data[DATA_COMPONENT] = comp
    from custom_components.advanced_google_contacts.calendar_sync import sync_events
    coord = next(iter(hass.data["advanced_google_contacts"].values()))
    fmt = {"birthday": "Geburtstag {name}[ - {age}]", "event": "{type} {name}"}
    await sync_events(hass, coord, "calendar.x", 12, ["birthday"], fmt)
    assert len(cal.events) == 1
    # Title format changes -> the old entry would have to be deleted.
    with pytest.raises(HomeAssistantError, match="Löschen"):
        await sync_events(hass, coord, "calendar.x", 12, ["birthday"], {**fmt, "birthday": "🎂 {name}"})
    assert len(cal.events) == 1, [e.summary for e in cal.events]


async def test_shrinking_range_leaves_stale_entries(hass, setup_integration, google, local_calendar):
    """Expected: entries of deleted contacts are removed even if they lie beyond a reduced range."""
    await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10)),
                             person("2", "Weg X", birthday=(1990, 6, 1))], create_contact_entities=False)
    await sync(hass, months=24)
    google.people = [person("1", "Anna Muster", birthday=(1990, 3, 10))]
    google.install()
    await sync(hass, months=6)
    titles = [t for _d, t, _x in await calendar_events(hass, local_calendar, end="2030-01-01")]
    assert not [t for t in titles if "Weg X" in t], titles


async def test_notes_below_marker_keep_entry_managed(hass, setup_integration, local_calendar):
    """Notes added below the first line keep the entry managed; a changed first line makes it unmanaged."""
    from .conftest import add_calendar_event
    await add_calendar_event(hass, local_calendar, "Geburtstag Anna Muster - 37", "2027-03-10", MARKER + "\nNotiz")
    await add_calendar_event(hass, local_calendar, "Geburtstag Anna Muster - 37", "2027-03-10", "Meine Notiz\n" + MARKER)
    await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10))], create_contact_entities=False)
    res = await sync(hass)
    assert res == {"desired": 1, "created": 0, "deleted": 0, "unchanged": 1}
    assert len(await calendar_events(hass, local_calendar)) == 2  # the second one is not ours


async def test_create_only_calendar_without_changes_works(hass, setup_integration):
    """A calendar without delete support is fine as long as nothing must be deleted."""
    await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10))], create_contact_entities=False)
    cal = CreateOnlyCal()
    comp = MagicMock(); comp.get_entity.return_value = cal
    hass.data[DATA_COMPONENT] = comp
    from custom_components.advanced_google_contacts.calendar_sync import sync_events
    coord = next(iter(hass.data["advanced_google_contacts"].values()))
    fmt = {"birthday": "Geburtstag {name}[ - {age}]", "event": "{type} {name}"}
    assert (await sync_events(hass, coord, "calendar.x", 12, ["birthday"], fmt))["created"] == 1
    assert (await sync_events(hass, coord, "calendar.x", 12, ["birthday"], fmt))["unchanged"] == 1


@pytest.mark.parametrize("start,months,expected", [
    ("2027-01-31", 1, "2027-02-28"), ("2028-01-31", 1, "2028-02-29"), ("2026-11-17", 2, "2027-01-17"),
    ("2026-12-31", 12, "2027-12-31"), ("2026-08-31", 6, "2027-02-28"), ("2026-11-17", 120, "2036-11-17"),
])
def test_add_months(start, months, expected):
    from custom_components.advanced_google_contacts.calendar_sync import add_months
    assert add_months(dt.date.fromisoformat(start), months) == dt.date.fromisoformat(expected)
