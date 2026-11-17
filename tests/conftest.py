"""Shared fixtures: a real Home Assistant with mocked Google endpoints.

Google is replaced by aioclient_mock (People API + OpenID UserInfo); the target
calendar is a real local_calendar entry, so the sync runs against HA's own
writable calendar implementation.
"""
from __future__ import annotations

import time
from typing import Any

import pytest
from homeassistant.components.application_credentials import ClientCredential, async_import_client_credential
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.advanced_google_contacts.const import DOMAIN, PROFILE_URL, URL

TZ = "Europe/Berlin"
NOW = "2026-11-17 12:00:00+01:00"
EMAIL = "tester@example.com"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def _recorder_before_hass(request):
    """Tests using recorder_mock need the database prepared before hass starts."""
    if "recorder_mock" in request.fixturenames:
        request.getfixturevalue("recorder_db_url")


@pytest.fixture(autouse=True)
async def base_setup(_recorder_before_hass, hass, freezer):
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone(TZ)
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(hass, DOMAIN, ClientCredential("client-id", "client-secret"), DOMAIN)


def person(rn: str, name: str | None, *, birthday=None, events=(), deleted=False, **extra) -> dict[str, Any]:
    """Build a People API person. birthday/event dates are (year|None, month, day)."""
    p: dict[str, Any] = {"resourceName": f"people/{rn}", "etag": "x", "metadata": {"deleted": deleted}}
    if name is not None:
        given, _, family = name.partition(" ")
        p["names"] = [{"displayName": name, "givenName": given, "familyName": family}]
    if birthday:
        y, m, d = birthday
        p["birthdays"] = [{"date": {k: v for k, v in (("year", y), ("month", m), ("day", d)) if v}}]
    if events:
        p["events"] = [
            {"type": t, "date": {k: v for k, v in (("year", y), ("month", m), ("day", d)) if v}}
            for t, (y, m, d) in events
        ]
    p.update(extra)
    return p


class FakeGoogle:
    """Controls the mocked Google responses."""

    def __init__(self, aioclient_mock):
        self.mock = aioclient_mock
        self.people: list[dict] = []
        self.page_size: int | None = None
        self.people_status = 200
        self.userinfo_status = 200
        self.userinfo_exc: Exception | None = None
        self.people_exc: Exception | None = None
        self.email = EMAIL

    def install(self):
        self.mock.clear_requests()
        if self.userinfo_exc:
            self.mock.get(PROFILE_URL, exc=self.userinfo_exc)
        else:
            self.mock.get(PROFILE_URL, status=self.userinfo_status, json={"email": self.email})
        if self.people_exc:
            self.mock.get(URL, exc=self.people_exc)
            return
        if self.people_status != 200:
            self.mock.get(URL, status=self.people_status, json={"error": "x"})
            return
        size = self.page_size or max(1, len(self.people))
        pages = [self.people[i:i + size] for i in range(0, len(self.people), size)] or [[]]
        # Later pages first: a request without pageToken must only match page 1.
        for idx in range(len(pages) - 1, 0, -1):
            body = {"connections": pages[idx]}
            if idx + 1 < len(pages):
                body["nextPageToken"] = f"p{idx + 1}"
            self.mock.get(f"{URL}?pageToken=p{idx}", json=body)
        first = {"connections": pages[0]}
        if len(pages) > 1:
            first["nextPageToken"] = "p1"
        self.mock.get(URL, json=first)

    def people_calls(self) -> int:
        return sum(1 for _m, url, *_ in self.mock.mock_calls if str(url).startswith(URL))


@pytest.fixture
def google(aioclient_mock) -> FakeGoogle:
    g = FakeGoogle(aioclient_mock)
    g.install()
    return g


def make_entry(hass, **options) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Advanced Google Contacts",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "ACCESS-SECRET",
                "refresh_token": "REFRESH-SECRET",
                "expires_at": time.time() + 3600,
                "token_type": "Bearer",
            },
        },
        options=options,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_integration(hass, google):
    async def _setup(people=(), **options):
        google.people = list(people)
        google.install()
        entry = make_entry(hass, **options)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry
    return _setup


@pytest.fixture
async def local_calendar(hass, tmp_path):
    # local_calendar writes an .ics file below the config dir.
    hass.config.config_dir = str(tmp_path)
    (tmp_path / ".storage").mkdir()
    entry = MockConfigEntry(domain="local_calendar", data={"calendar_name": "Geburtstage", "storage_key": "geburtstage"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("calendar.geburtstage")
    return "calendar.geburtstage"


async def calendar_events(hass, entity_id, start="2026-11-01", end="2029-12-31"):
    """All events of a calendar as sorted (date, summary, description)."""
    res = await hass.services.async_call(
        "calendar", "get_events",
        {"entity_id": entity_id, "start_date_time": f"{start} 00:00:00", "end_date_time": f"{end} 00:00:00"},
        blocking=True, return_response=True,
    )
    return sorted((e["start"], e["summary"], e.get("description")) for e in res[entity_id]["events"])


async def add_calendar_event(hass, entity_id, summary, date, description=None):
    import datetime as dt
    d = dt.date.fromisoformat(date)
    data = {"entity_id": entity_id, "summary": summary, "start_date": d.isoformat(), "end_date": (d + dt.timedelta(days=1)).isoformat()}
    if description is not None:
        data["description"] = description
    await hass.services.async_call("calendar", "create_event", data, blocking=True)


async def sync(hass, service="sync_events_from_google_contacts", **data):
    data.setdefault("calendar", "calendar.geburtstage")
    data.setdefault("months", 12)
    return await hass.services.async_call(DOMAIN, service, data, blocking=True, return_response=True)
