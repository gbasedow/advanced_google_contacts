"""Diagnostics download for Advanced Google Contacts.

Contains no contact data: only counts, settings and the last sync outcome.
Names of contacts that appear in a stored error message are redacted.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration

from .calendar_sync import CUSTOM_PREFIX, event_type_key
from .const import DOMAIN

REDACTED = "**REDACTED**"
TO_REDACT = {"token", "access_token", "refresh_token", "id_token", "title", "unique_id"}


def _contact_stats(contacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fields: Counter[str] = Counter()
    events: Counter[str] = Counter()
    custom_labels: set[str] = set()
    birthdays = birthdays_with_year = 0
    for contact in contacts.values():
        for field, value in contact.items():
            if value and field not in ("resource_name", "display_name"):
                fields[field] += 1
        items = [b for b in contact.get("birthdays") or [] if isinstance(b, dict)]
        if items:
            birthdays += 1
            if any((b.get("date") or {}).get("year") for b in items):
                birthdays_with_year += 1
        for raw in contact.get("events") or []:
            if not isinstance(raw, dict):
                continue
            key = event_type_key(raw)
            if key.startswith(CUSTOM_PREFIX):
                custom_labels.add(key)
                key = "custom"
            events[key] += 1
    return {
        "total": len(contacts),
        "with_birthday": birthdays,
        "with_birthday_year": birthdays_with_year,
        "events_by_type": dict(sorted(events.items())),
        "distinct_custom_event_labels": len(custom_labels),
        "contacts_per_field": dict(sorted(fields.items())),
    }


def _redact_names(value: Any, names: list[str]) -> Any:
    if isinstance(value, str):
        for name in names:
            value = value.replace(name, REDACTED)
        return value
    if isinstance(value, dict):
        return {k: _redact_names(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_names(v, names) for v in value]
    return value


async def async_get_config_entry_diagnostics(hass, entry) -> dict[str, Any]:
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    contacts = (coordinator.data or {}) if coordinator else {}
    # Longest first, so "Anna Muster" is replaced before "Anna".
    names = sorted(
        {str(c.get("display_name") or "").strip() for c in contacts.values()} - {""},
        key=len,
        reverse=True,
    )
    integration = await async_get_integration(hass, DOMAIN)
    issues = [
        issue_id
        for (domain, issue_id) in ir.async_get(hass).issues
        if domain == DOMAIN
    ]
    return {
        "integration_version": str(integration.version),
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator": None if coordinator is None else {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval) if coordinator.update_interval else None,
            "last_exception": repr(coordinator.last_exception) if coordinator.last_exception else None,
        },
        "contacts": _contact_stats(contacts),
        "last_sync": _redact_names(coordinator.last_sync, names) if coordinator else None,
        "repair_issues": sorted(issues),
    }
