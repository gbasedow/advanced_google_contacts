import datetime as dt
from unittest.mock import MagicMock

from homeassistant.components.calendar import DATA_COMPONENT, CalendarEntity, CalendarEntityFeature, CalendarEvent
from homeassistant.util import dt as dt_util


class FakeCal(CalendarEntity):
    _attr_supported_features = CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT

    def __init__(self, keep_description=True):
        self.events, self.n, self.keep_description = {}, 0, keep_description

    def add(self, summary, date, description=None):
        self.n += 1
        uid = f"u{self.n}"
        self.events[uid] = CalendarEvent(start=date, end=date + dt.timedelta(days=1), summary=summary,
                                         description=description if self.keep_description else None, uid=uid)
        return uid

    @property
    def event(self):
        return None

    async def async_get_events(self, hass, start, end):
        return [e for e in self.events.values() if start.date() <= e.start < end.date()]

    async def async_create_event(self, **kw):
        self.add(kw["summary"], kw["dtstart"], kw.get("description"))

    async def async_delete_event(self, uid, recurrence_id=None, recurrence_range=None):
        del self.events[uid]

    def summaries(self):
        return sorted((e.summary, e.description) for e in self.events.values())


class FakeCoord:
    def __init__(self, contacts=None, exc=None, entry=None):
        self.contacts, self.exc = contacts, exc
        self.entry = entry or MagicMock(options={})
        self.data = contacts
        self.last_sync = None
        self.last_update_success = True
        self.update_interval = None
        self.last_exception = None

    async def async_fetch_contacts(self):
        if self.exc:
            raise self.exc
        return self.contacts

    def async_set_updated_data(self, data):
        self.data = data


def d(y, m, day):
    out = {"month": m, "day": day}
    if y:
        out["year"] = y
    return {"date": out}


def contact(name, birthday=None, events=(), given="", family=""):
    c = {"display_name": name, "names": [{"displayName": name, "givenName": given, "familyName": family}]}
    if birthday:
        c["birthdays"] = [d(*birthday)]
    if events:
        c["events"] = [{**d(*date), "type": typ} for typ, date in events]
    return c


def setup_cal(hass, cal):
    comp = MagicMock()
    comp.get_entity.return_value = cal
    hass.data[DATA_COMPONENT] = comp


def nxt(m, day):
    today = dt_util.now().date()
    x = dt.date(today.year, m, day)
    return x if x >= today else dt.date(today.year + 1, m, day)
