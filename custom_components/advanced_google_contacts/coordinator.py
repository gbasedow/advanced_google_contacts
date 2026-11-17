from datetime import timedelta
import logging

from aiohttp import ClientError, ClientResponseError

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import API

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=30)


class Coordinator(DataUpdateCoordinator):
    """Holds the Google contacts.

    Periodic polling is only needed while contact entities exist. Without
    entities the data is fetched once at setup and freshly for every birthday
    sync, so ``poll`` is False and no background requests are made.
    """

    def __init__(self, hass, entry, oauth, poll=True):
        self.entry = entry
        self.api = API(oauth)
        # Outcome of the last calendar sync, shown in the diagnostics download.
        self.last_sync = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Advanced Google Contacts",
            update_interval=UPDATE_INTERVAL if poll else None,
        )

    async def async_account_email(self):
        return await self.api.account_email()

    async def async_fetch_contacts(self):
        """Fetch contacts now; errors are raised instead of being logged.

        Raises ConfigEntryAuthFailed for 401/403 and UpdateFailed otherwise.
        """
        try:
            return await self.api.contacts()
        except ClientResponseError as e:
            if e.status in (401, 403):
                raise ConfigEntryAuthFailed(f"Google authorization failed: HTTP {e.status}") from e
            raise UpdateFailed(f"Google People API HTTP {e.status}") from e
        except ClientError as e:
            raise UpdateFailed(str(e)) from e
        except TimeoutError as e:
            raise UpdateFailed("Google People API timeout") from e

    async def _async_update_data(self):
        return await self.async_fetch_contacts()
