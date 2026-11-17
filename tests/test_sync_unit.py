import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.advanced_google_contacts.calendar_sync import MARKER, marker_for, sync_events
from .fakes import FakeCal, FakeCoord, contact, nxt, setup_cal

LEGACY = "Synchronisiert aus Google Contacts Basedog"
FMT = {"birthday": "Geburtstag {name}[ - {age}]", "event": "{type} {name}[ - {age}]"}


async def run(hass, coord, types=("birthday",), fmt=FMT, months=12):
    return await sync_events(hass, coord, "calendar.x", months, list(types), fmt)


async def test_legacy_and_v02_birthdays_unchanged(hass):
    """Entries from 4.7 and 0.2.0 with the default format are kept, not recreated."""
    cal = FakeCal(); setup_cal(hass, cal)
    a, c = nxt(3, 10), nxt(5, 5)
    ua = cal.add(f"Geburtstag Anna - {a.year - 1990}", a, LEGACY)
    uc = cal.add("Geburtstag Carl", c, MARKER)
    coord = FakeCoord({"1": contact("Anna", (1990, 3, 10)), "2": contact("Carl", (None, 5, 5))})
    assert await run(hass, coord) == {"desired": 2, "created": 0, "deleted": 0, "unchanged": 2}
    assert set(cal.events) == {ua, uc}


async def test_manual_entries_untouched_and_idempotent(hass):
    cal = FakeCal(); setup_cal(hass, cal)
    a = nxt(3, 10)
    manual = cal.add("Geburtstag Anna - 1", a, None)
    old = cal.add("Geburtstag Anna - 1", a, MARKER)
    coord = FakeCoord({"1": contact("Anna", (1990, 3, 10))})
    res = await run(hass, coord)
    assert res == {"desired": 1, "created": 1, "deleted": 1, "unchanged": 0}
    assert manual in cal.events and old not in cal.events
    assert await run(hass, coord) == {"desired": 1, "created": 0, "deleted": 0, "unchanged": 1}


async def test_event_types_and_scope(hass):
    cal = FakeCal(); setup_cal(hass, cal)
    a, w, o, b = nxt(3, 10), nxt(6, 1), nxt(7, 2), nxt(8, 3)
    coord = FakeCoord({"1": contact("Anna", (1990, 3, 10), events=[
        ("anniversary", (2010, 6, 1)), ("Hochzeitstag", (2012, 7, 2)), ("other", (None, 8, 3))])})
    res = await run(hass, coord, ["birthday", "anniversary", "custom", "other"])
    assert res["created"] == 4
    assert cal.summaries() == sorted([
        (f"Geburtstag Anna - {a.year - 1990}", MARKER),
        (f"Jahrestag Anna - {w.year - 2010}", marker_for("anniversary")),
        (f"Hochzeitstag Anna - {o.year - 2012}", marker_for("custom:Hochzeitstag")),
        ("Ereignis Anna", marker_for("other")),
    ])
    # A birthday-only sync must not touch the other types.
    assert (await run(hass, coord))["deleted"] == 0
    assert len(cal.events) == 4
    # Selecting a single custom label by name works too; nothing to change.
    assert (await run(hass, coord, ["hochzeitstag"]))["unchanged"] == 1
    # Removing the anniversary from the contact deletes only that entry.
    coord.contacts["1"]["events"] = [e for e in coord.contacts["1"]["events"] if e["type"] != "anniversary"]
    res = await run(hass, coord, ["all"])
    assert res["deleted"] == 1 and len(cal.events) == 3


async def test_title_format_change_replaces_entries(hass):
    cal = FakeCal(); setup_cal(hass, cal)
    a = nxt(3, 10)
    coord = FakeCoord({"1": contact("Anna Muster", (1990, 3, 10), given="Anna", family="Muster")})
    await run(hass, coord)
    res = await run(hass, coord, fmt={"birthday": "🎂 {first_name}[ ({age})]", "event": "x {name}"})
    assert res == {"desired": 1, "created": 1, "deleted": 1, "unchanged": 0}
    assert cal.summaries() == [(f"🎂 Anna ({a.year - 1990})", MARKER)]


async def test_birthday_with_and_without_year_dedup(hass):
    cal = FakeCal(); setup_cal(hass, cal)
    a = nxt(3, 10)
    c = contact("Anna")
    c["birthdays"] = [{"date": {"month": 3, "day": 10}}, {"date": {"year": 1990, "month": 3, "day": 10}}]
    res = await run(hass, FakeCoord({"1": c}))
    assert res["desired"] == 1
    assert cal.summaries() == [(f"Geburtstag Anna - {a.year - 1990}", MARKER)]


@pytest.mark.parametrize("coord", [FakeCoord(exc=UpdateFailed("boom")), FakeCoord(contacts={})])
async def test_abort_without_changes(hass, coord):
    cal = FakeCal(); setup_cal(hass, cal)
    uid = cal.add("Geburtstag Anna - 1", nxt(3, 10), MARKER)
    with pytest.raises(HomeAssistantError):
        await run(hass, coord)
    assert list(cal.events) == [uid]


async def test_auth_failure_starts_reauth(hass):
    cal = FakeCal(); setup_cal(hass, cal)
    coord = FakeCoord(exc=ConfigEntryAuthFailed("x"))
    with pytest.raises(HomeAssistantError):
        await run(hass, coord)
    coord.entry.async_start_reauth.assert_called_once_with(hass)


async def test_calendar_without_descriptions_deletes_nothing(hass):
    cal = FakeCal(keep_description=False); setup_cal(hass, cal)
    uid = cal.add("Geburtstag Zoe - 3", nxt(6, 1))
    with pytest.raises(HomeAssistantError, match="ohne Beschreibung"):
        await run(hass, FakeCoord({"1": contact("Anna", (1990, 3, 10))}))
    assert uid in cal.events


async def test_empty_selection_rejected(hass):
    cal = FakeCal(); setup_cal(hass, cal)
    with pytest.raises(HomeAssistantError):
        await run(hass, FakeCoord({"1": contact("Anna", (1990, 3, 10))}), types=[" "])
