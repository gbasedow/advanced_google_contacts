"""Reliable birthday synchronization for writable Home Assistant calendars."""
from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Any

from dateutil.relativedelta import relativedelta

from homeassistant.components.calendar import DATA_COMPONENT, CalendarEntity, CalendarEntityFeature
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)
RX = re.compile(r"^Geburtstag (?P<name>.+?)(?: - (?P<age>\d+))?$")

# Description written into every created event. Only events carrying one of
# these markers are treated as managed (compared, deduplicated, deleted);
# all other events in the calendar are never touched.
MARKER = "Synchronisiert aus Advanced Google Contacts"
LEGACY_MARKERS = ("Synchronisiert aus Google Contacts Basedog",)
MARKERS = (MARKER, *LEGACY_MARKERS)


def managed_match(event) -> re.Match | None:
    """Return the title match if the event was created by this sync."""
    if (getattr(event, "description", None) or "").strip() not in MARKERS:
        return None
    return RX.fullmatch(event.summary or "")


def event_date(value: dt.date | dt.datetime) -> dt.date:
    return dt_util.as_local(value).date() if isinstance(value, dt.datetime) else value


def birthday_date(item: dict[str, Any]) -> tuple[int | None, int, int] | None:
    data = item.get("date") or {}
    month, day, year = data.get("month"), data.get("day"), data.get("year")
    if not isinstance(month, int) or not isinstance(day, int):
        return None
    return (year if isinstance(year, int) else None, month, day)


def occurrence(month: int, day: int, year: int) -> dt.date | None:
    try:
        return dt.date(year, month, day)
    except ValueError:
        # Deterministic policy for Feb 29 birthdays in non-leap years.
        return dt.date(year, 2, 28) if (month, day) == (2, 29) else None


def summary(name: str, birth_year: int | None, year: int) -> str:
    return f"Geburtstag {name} - {year - birth_year}" if birth_year is not None else f"Geburtstag {name}"


def desired_birthdays(contacts: dict[str, dict[str, Any]], start: dt.date, end: dt.date) -> dict[tuple[str, dt.date], str]:
    """Build desired events. Naming scheme intentionally defines identity, per user requirement."""
    desired: dict[tuple[str, dt.date], str] = {}
    for contact in contacts.values():
        name = str(contact.get("display_name") or "Unbenannter Kontakt").strip()
        seen: set[tuple[int | None, int, int]] = set()
        for raw in contact.get("birthdays") or []:
            parsed = birthday_date(raw)
            if parsed is None or parsed in seen:
                continue
            seen.add(parsed)
            birth_year, month, day = parsed
            for year in range(start.year, end.year + 1):
                date = occurrence(month, day, year)
                if date is not None and start <= date <= end:
                    desired[(name, date)] = summary(name, birth_year, year)
    return desired


async def _read(cal: CalendarEntity, hass, start: dt.date, end: dt.date):
    start_dt = dt_util.start_of_local_day(start)
    end_dt = dt_util.start_of_local_day(end + dt.timedelta(days=1))
    try:
        return await cal.async_get_events(hass, start_dt, end_dt)
    except Exception as err:
        raise HomeAssistantError(f"Geburtstags-Sync: Kalender konnte nicht gelesen werden: {err}") from err


async def sync_birthdays(hass, coordinator, calendar_entity_id: str, months: int) -> dict[str, int]:
    """Create desired events first, verify, then remove stale/duplicate managed events."""
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError("Geburtstags-Sync: Kalender-Integration ist nicht geladen.")

    cal = component.get_entity(calendar_entity_id)
    if cal is None or not isinstance(cal, CalendarEntity):
        raise HomeAssistantError(f"Geburtstags-Sync: {calendar_entity_id} ist keine verfügbare Kalender-Entität.")

    features = cal.supported_features or 0
    if not features & CalendarEntityFeature.CREATE_EVENT:
        raise HomeAssistantError("Geburtstags-Sync: Der gewählte Kalender unterstützt das Erstellen von Terminen nicht.")

    # Always work on freshly fetched contacts. Any error aborts the sync before
    # the calendar is touched, so stale data can never cause deletions.
    try:
        contacts = await coordinator.async_fetch_contacts()
    except ConfigEntryAuthFailed as err:
        coordinator.entry.async_start_reauth(hass)
        raise HomeAssistantError(
            "Geburtstags-Sync: Google-Anmeldung abgelaufen, bitte die Integration neu authentifizieren."
        ) from err
    except UpdateFailed as err:
        raise HomeAssistantError(f"Geburtstags-Sync: Google-Kontakte konnten nicht geladen werden: {err}") from err
    if not contacts:
        raise HomeAssistantError(
            "Geburtstags-Sync: Google hat keine Kontakte geliefert. Aus Sicherheitsgründen wird nichts geändert."
        )
    coordinator.async_set_updated_data(contacts)

    today = dt_util.now().date()
    range_end = today + relativedelta(months=months)
    desired = desired_birthdays(contacts, today, range_end)

    # Phase 1: read and create missing events. No deletion happens before all creates succeed.
    existing = await _read(cal, hass, today, range_end)
    exact_existing: set[tuple[str, dt.date, str]] = set()
    for event in existing:
        match = managed_match(event)
        if match:
            exact_existing.add((match.group("name"), event_date(event.start), event.summary))

    created = 0
    for (name, date), wanted_summary in sorted(desired.items(), key=lambda item: (item[0][1], item[0][0].casefold())):
        if (name, date, wanted_summary) in exact_existing:
            continue
        try:
            # CalendarEntity's native API uses dtstart/dtend, also for all-day dates.
            await cal.async_create_event(
                summary=wanted_summary,
                dtstart=date,
                dtend=date + dt.timedelta(days=1),
                description=MARKER,
            )
            created += 1
        except Exception as err:
            raise HomeAssistantError(
                f'Geburtstags-Sync: Termin "{wanted_summary}" am {date.isoformat()} konnte nicht erstellt werden: {err}'
            ) from err

    # Re-read after creation. This verifies persistence and gives us UIDs for cleanup.
    after_create = await _read(cal, hass, today, range_end)

    # Determine stale/duplicate events. One exact desired event is retained.
    kept: set[tuple[str, dt.date]] = set()
    to_delete = []
    for event in after_create:
        match = managed_match(event)
        if not match:
            continue
        key = (match.group("name"), event_date(event.start))
        wanted = desired.get(key)
        if wanted == event.summary and key not in kept:
            kept.add(key)
        else:
            to_delete.append(event)

    # Every desired event must have been observable before cleanup.
    missing_after_create = [wanted for key, wanted in desired.items() if key not in kept]
    if missing_after_create:
        sample = ", ".join(missing_after_create[:3])
        raise HomeAssistantError(
            "Geburtstags-Sync: Der Kalender hat neu erstellte Termine beim Kontrolllesen nicht "
            "(oder ohne Beschreibung) zurückgegeben. Es wird aus Sicherheitsgründen nichts gelöscht. "
            f"Beispiele: {sample}"
        )

    deleted = 0
    if to_delete:
        if not features & CalendarEntityFeature.DELETE_EVENT:
            raise HomeAssistantError(
                f"Geburtstags-Sync: {len(to_delete)} veraltete oder doppelte Geburtstagseinträge müssten gelöscht werden, "
                "aber der gewählte Kalender unterstützt das Löschen über Home Assistant nicht. "
                "Neue/korrekte Einträge wurden nicht absichtlich entfernt."
            )
        for event in to_delete:
            if not event.uid:
                raise HomeAssistantError(
                    f'Geburtstags-Sync: "{event.summary}" kann nicht sicher gelöscht werden, weil der Kalender keine UID liefert.'
                )
            try:
                await cal.async_delete_event(event.uid, recurrence_id=event.recurrence_id)
                deleted += 1
            except Exception as err:
                raise HomeAssistantError(
                    f'Geburtstags-Sync: "{event.summary}" konnte nicht gelöscht werden: {err}'
                ) from err

    # Final verification: exactly one correctly named event per desired birthday.
    final_events = await _read(cal, hass, today, range_end)
    counts: dict[tuple[str, dt.date, str], int] = {}
    for event in final_events:
        match = managed_match(event)
        if match:
            k = (match.group("name"), event_date(event.start), event.summary)
            counts[k] = counts.get(k, 0) + 1

    problems = []
    for (name, date), wanted in desired.items():
        count = counts.get((name, date, wanted), 0)
        if count != 1:
            problems.append(f"{wanted} ({date.isoformat()}): {count} Treffer")
    if problems:
        raise HomeAssistantError(
            "Geburtstags-Sync: Abschlussprüfung fehlgeschlagen. " + "; ".join(problems[:5])
        )

    try:
        cal.async_update_event_listeners()
    except AttributeError:
        pass

    unchanged = len(desired) - created
    _LOGGER.info(
        "Birthday sync complete: calendar=%s desired=%d created=%d deleted=%d unchanged=%d",
        calendar_entity_id, len(desired), created, deleted, max(0, unchanged),
    )
    return {"desired": len(desired), "created": created, "deleted": deleted, "unchanged": max(0, unchanged)}
