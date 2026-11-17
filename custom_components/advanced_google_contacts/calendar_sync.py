"""Synchronize birthdays and other contact events into a writable HA calendar.

Every created entry carries a marker in its description. Only entries with a
marker of a selected event type are compared, deduplicated or deleted; all
other entries in the calendar are never touched. An entry is identified by
(date, title, event type), so changing the title format replaces the entries.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from dateutil.relativedelta import relativedelta

from homeassistant.components.calendar import DATA_COMPONENT, CalendarEntity, CalendarEntityFeature
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    EVENT_TYPE_ALL,
    EVENT_TYPE_ANNIVERSARY,
    EVENT_TYPE_BIRTHDAY,
    EVENT_TYPE_CUSTOM,
    EVENT_TYPE_LABELS,
    EVENT_TYPE_OTHER,
)
from .title_format import render_title

_LOGGER = logging.getLogger(__name__)

# Birthday entries keep the plain marker used since 0.2.0, so existing entries
# stay valid. Other types carry their type key: "<MARKER> [anniversary]".
MARKER = "Synchronisiert aus Advanced Google Contacts"
LEGACY_MARKERS = ("Synchronisiert aus Google Contacts Basedog",)
CUSTOM_PREFIX = f"{EVENT_TYPE_CUSTOM}:"

Key = tuple[dt.date, str, str]  # (date, title, event type key)


def marker_for(type_key: str) -> str:
    return MARKER if type_key == EVENT_TYPE_BIRTHDAY else f"{MARKER} [{type_key}]"


def managed_type(event) -> str | None:
    """Event type key of an entry created by this sync, else None."""
    description = (getattr(event, "description", None) or "").strip()
    if description == MARKER or description in LEGACY_MARKERS:
        return EVENT_TYPE_BIRTHDAY
    prefix = f"{MARKER} ["
    if description.startswith(prefix) and description.endswith("]") and len(description) > len(prefix) + 1:
        return description[len(prefix):-1]
    return None


def event_type_key(item: dict[str, Any]) -> str:
    """Type key of a Google contact event: anniversary, other or custom:<label>."""
    raw = str(item.get("type") or "").strip()
    if not raw or raw.casefold() == EVENT_TYPE_OTHER:
        return EVENT_TYPE_OTHER
    if raw.casefold() == EVENT_TYPE_ANNIVERSARY:
        return EVENT_TYPE_ANNIVERSARY
    return f"{CUSTOM_PREFIX}{raw}"


def type_label(type_key: str) -> str:
    if type_key.startswith(CUSTOM_PREFIX):
        return type_key[len(CUSTOM_PREFIX):]
    return EVENT_TYPE_LABELS.get(type_key, type_key)


def normalize_selection(event_types) -> frozenset[str]:
    selected = {str(t).strip() for t in event_types if str(t).strip()}
    if not selected:
        raise HomeAssistantError("Kalender-Sync: Es wurde kein Ereignistyp ausgewählt.")
    return frozenset(selected)


def type_selected(type_key: str, selected: frozenset[str]) -> bool:
    """birthday/anniversary/other by key; 'custom' = every own label; any other
    value = this own label (case-insensitive); 'all' = everything."""
    if EVENT_TYPE_ALL in selected or type_key in selected:
        return True
    if type_key.startswith(CUSTOM_PREFIX):
        label = type_key[len(CUSTOM_PREFIX):].casefold()
        return EVENT_TYPE_CUSTOM in selected or label in {s.casefold() for s in selected}
    return False


def event_date(value: dt.date | dt.datetime) -> dt.date:
    return dt_util.as_local(value).date() if isinstance(value, dt.datetime) else value


def parse_date(item: dict[str, Any]) -> tuple[int | None, int, int] | None:
    data = item.get("date") or {}
    month, day, year = data.get("month"), data.get("day"), data.get("year")
    if not isinstance(month, int) or not isinstance(day, int):
        return None
    return (year if isinstance(year, int) and year > 0 else None, month, day)


def occurrence(month: int, day: int, year: int) -> dt.date | None:
    try:
        return dt.date(year, month, day)
    except ValueError:
        # Deterministic policy for Feb 29 in non-leap years.
        return dt.date(year, 2, 28) if (month, day) == (2, 29) else None


def _names(contact: dict[str, Any]) -> tuple[str, str, str]:
    name = str(contact.get("display_name") or "Unbenannter Kontakt").strip()
    first = last = ""
    for entry in contact.get("names") or []:
        if isinstance(entry, dict):
            first = str(entry.get("givenName") or "").strip()
            last = str(entry.get("familyName") or "").strip()
            break
    return name, first, last


def desired_events(
    contacts: dict[str, dict[str, Any]],
    start: dt.date,
    end: dt.date,
    selected: frozenset[str],
    formats: dict[str, str],
) -> dict[tuple[dt.date, str], str]:
    """Return {(date, title): type key} for all entries in [start, end]."""
    desired: dict[tuple[dt.date, str], str] = {}
    for contact in contacts.values():
        name, first, last = _names(contact)
        items: list[tuple[str, dict]] = []
        if type_selected(EVENT_TYPE_BIRTHDAY, selected):
            items += [(EVENT_TYPE_BIRTHDAY, raw) for raw in contact.get("birthdays") or []]
        for raw in contact.get("events") or []:
            key = event_type_key(raw)
            if type_selected(key, selected):
                items.append((key, raw))

        # One date per (type, month, day); an entry with year wins over one without.
        dates: dict[tuple[str, int, int], int | None] = {}
        for key, raw in items:
            parsed = parse_date(raw if isinstance(raw, dict) else {})
            if parsed is None:
                continue
            year, month, day = parsed
            if dates.get((key, month, day)) is None:
                dates[(key, month, day)] = year

        for (key, month, day), origin_year in dates.items():
            fmt = formats[EVENT_TYPE_BIRTHDAY] if key == EVENT_TYPE_BIRTHDAY else formats["event"]
            for year in range(start.year, end.year + 1):
                date = occurrence(month, day, year)
                if date is None or not start <= date <= end:
                    continue
                age = year - origin_year if origin_year is not None and year >= origin_year else None
                title = render_title(fmt, {
                    "name": name, "first_name": first, "last_name": last,
                    "type": type_label(key),
                    "age": "" if age is None else str(age),
                    "year": "" if origin_year is None else str(origin_year),
                })
                if title:
                    desired[(date, title)] = key
    return desired


async def _read(cal: CalendarEntity, hass, start: dt.date, end: dt.date):
    start_dt = dt_util.start_of_local_day(start)
    end_dt = dt_util.start_of_local_day(end + dt.timedelta(days=1))
    try:
        return await cal.async_get_events(hass, start_dt, end_dt)
    except Exception as err:
        raise HomeAssistantError(f"Kalender-Sync: Kalender konnte nicht gelesen werden: {err}") from err


def _managed(events, selected) -> list[tuple[Key, Any]]:
    out = []
    for event in events:
        key = managed_type(event)
        if key is not None and type_selected(key, selected):
            out.append(((event_date(event.start), event.summary or "", key), event))
    return out


async def sync_events(
    hass,
    coordinator,
    calendar_entity_id: str,
    months: int,
    event_types,
    formats: dict[str, str],
) -> dict[str, Any]:
    """Create desired entries first, verify, then remove stale/duplicate managed entries."""
    selected = normalize_selection(event_types)

    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError("Kalender-Sync: Kalender-Integration ist nicht geladen.")
    cal = component.get_entity(calendar_entity_id)
    if cal is None or not isinstance(cal, CalendarEntity):
        raise HomeAssistantError(f"Kalender-Sync: {calendar_entity_id} ist keine verfügbare Kalender-Entität.")
    features = cal.supported_features or 0
    if not features & CalendarEntityFeature.CREATE_EVENT:
        raise HomeAssistantError("Kalender-Sync: Der gewählte Kalender unterstützt das Erstellen von Terminen nicht.")

    # Always work on freshly fetched contacts. Any error aborts the sync before
    # the calendar is touched, so stale data can never cause deletions.
    try:
        contacts = await coordinator.async_fetch_contacts()
    except ConfigEntryAuthFailed as err:
        coordinator.entry.async_start_reauth(hass)
        raise HomeAssistantError(
            "Kalender-Sync: Google-Anmeldung abgelaufen, bitte die Integration neu authentifizieren."
        ) from err
    except UpdateFailed as err:
        raise HomeAssistantError(f"Kalender-Sync: Google-Kontakte konnten nicht geladen werden: {err}") from err
    if not contacts:
        raise HomeAssistantError(
            "Kalender-Sync: Google hat keine Kontakte geliefert. Aus Sicherheitsgründen wird nichts geändert."
        )
    coordinator.async_set_updated_data(contacts)

    today = dt_util.now().date()
    range_end = today + relativedelta(months=months)
    desired = desired_events(contacts, today, range_end, selected, formats)
    wanted: set[Key] = {(date, title, key) for (date, title), key in desired.items()}

    # Phase 1: create missing entries. Nothing is deleted before all creates succeed.
    existing = {key for key, _event in _managed(await _read(cal, hass, today, range_end), selected)}
    created = 0
    for date, title, key in sorted(wanted, key=lambda k: (k[0], k[1].casefold())):
        if (date, title, key) in existing:
            continue
        try:
            # CalendarEntity's native API uses dtstart/dtend, also for all-day dates.
            await cal.async_create_event(
                summary=title,
                dtstart=date,
                dtend=date + dt.timedelta(days=1),
                description=marker_for(key),
            )
            created += 1
        except Exception as err:
            raise HomeAssistantError(
                f'Kalender-Sync: Termin "{title}" am {date.isoformat()} konnte nicht erstellt werden: {err}'
            ) from err

    # Phase 2: re-read; every wanted entry must be visible before anything is deleted.
    kept: set[Key] = set()
    to_delete = []
    for key, event in _managed(await _read(cal, hass, today, range_end), selected):
        if key in wanted and key not in kept:
            kept.add(key)
        else:
            to_delete.append(event)
    missing = sorted(wanted - kept)
    if missing:
        sample = ", ".join(title for _date, title, _key in missing[:3])
        raise HomeAssistantError(
            "Kalender-Sync: Der Kalender hat neu erstellte Termine beim Kontrolllesen nicht "
            "(oder ohne Beschreibung) zurückgegeben. Es wird aus Sicherheitsgründen nichts gelöscht. "
            f"Beispiele: {sample}"
        )

    deleted = 0
    if to_delete:
        if not features & CalendarEntityFeature.DELETE_EVENT:
            raise HomeAssistantError(
                f"Kalender-Sync: {len(to_delete)} veraltete oder doppelte Einträge müssten gelöscht werden, "
                "aber der gewählte Kalender unterstützt das Löschen über Home Assistant nicht. "
                "Neue/korrekte Einträge wurden nicht absichtlich entfernt."
            )
        for event in to_delete:
            if not event.uid:
                raise HomeAssistantError(
                    f'Kalender-Sync: "{event.summary}" kann nicht sicher gelöscht werden, weil der Kalender keine UID liefert.'
                )
            try:
                await cal.async_delete_event(event.uid, recurrence_id=event.recurrence_id)
                deleted += 1
            except Exception as err:
                raise HomeAssistantError(
                    f'Kalender-Sync: "{event.summary}" konnte nicht gelöscht werden: {err}'
                ) from err

    # Final verification: exactly one entry per wanted key.
    counts: dict[Key, int] = {}
    for key, _event in _managed(await _read(cal, hass, today, range_end), selected):
        counts[key] = counts.get(key, 0) + 1
    problems = [
        f"{title} ({date.isoformat()}): {counts.get((date, title, key), 0)} Treffer"
        for date, title, key in sorted(wanted)
        if counts.get((date, title, key), 0) != 1
    ]
    if problems:
        raise HomeAssistantError("Kalender-Sync: Abschlussprüfung fehlgeschlagen. " + "; ".join(problems[:5]))

    try:
        cal.async_update_event_listeners()
    except AttributeError:
        pass

    unchanged = max(0, len(wanted) - created)
    _LOGGER.info(
        "Calendar sync complete: calendar=%s types=%s desired=%d created=%d deleted=%d unchanged=%d",
        calendar_entity_id, sorted(selected), len(wanted), created, deleted, unchanged,
    )
    return {"desired": len(wanted), "created": created, "deleted": deleted, "unchanged": unchanged}
