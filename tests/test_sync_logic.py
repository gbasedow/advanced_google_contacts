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


async def test_edited_description_makes_entry_unmanaged(hass, setup_integration, local_calendar):
    """Documented behaviour: an entry whose description was edited is no longer managed (a new one is created)."""
    from .conftest import add_calendar_event
    await add_calendar_event(hass, local_calendar, "Geburtstag Anna Muster - 37", "2027-03-10", MARKER + "\nNotiz")
    await setup_integration([person("1", "Anna Muster", birthday=(1990, 3, 10))], create_contact_entities=False)
    res = await sync(hass)
    assert res["created"] == 1  # duplicate in the calendar
    assert len(await calendar_events(hass, local_calendar)) == 2
