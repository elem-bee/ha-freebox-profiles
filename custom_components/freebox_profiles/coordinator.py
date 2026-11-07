"""Data update coordinator for Freebox Profiles."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    FreeboxAuthError,
    FreeboxClient,
    FreeboxError,
    FreeboxPermissionError,
)
from .connections import (
    ConnectionTracker,
    async_announce_connections,
    offline_delay_seconds,
)
from .const import DOMAIN, PROFILE_UPDATE_KEYS, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type FreeboxProfilesConfigEntry = ConfigEntry[FreeboxProfilesCoordinator]


class FreeboxProfilesCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Poll the profiles of a Freebox."""

    config_entry: FreeboxProfilesConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: FreeboxProfilesConfigEntry,
        client: FreeboxClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self._tracker = ConnectionTracker(lambda: offline_delay_seconds(entry))

    @property
    def _issue_id(self) -> str:
        return f"missing_permission_{self.config_entry.entry_id}"

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Fetch all profiles."""
        try:
            profiles = await self.client.async_get_profiles()
        except FreeboxAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FreeboxPermissionError as err:
            # Log in again next time, so that a permission granted in
            # Freebox OS in the meantime is taken into account.
            self.client.invalidate_session()
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="missing_permission",
                translation_placeholders={"title": self.config_entry.title},
            )
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="missing_permission"
            ) from err
        except FreeboxError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)
        data = {
            int(profile["profile_id"]): profile
            for profile in profiles
            if "profile_id" in profile
        }
        if connected := self._tracker.update(data):
            async_announce_connections(self.hass, self.config_entry, connected)
        return data

    async def async_set_override(
        self,
        profile_id: int,
        override: bool,
        mode: str | None = None,
        until: int = 0,
    ) -> None:
        """Pause, allow or return a profile to its planning.

        until is a Unix timestamp, 0 meaning "no time limit".
        """
        profile = self.data.get(profile_id)
        if profile is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_profile",
                translation_placeholders={"profile_id": str(profile_id)},
            )
        # Freebox OS sends the whole profile back: keep the device list.
        payload = {key: profile[key] for key in PROFILE_UPDATE_KEYS if key in profile}
        payload["override"] = override
        if override:
            payload["override_mode"] = mode
            payload["override_until"] = until

        try:
            await self.client.async_update_profile(profile_id, payload)
        except FreeboxPermissionError as err:
            self.client.invalidate_session()
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="missing_permission"
            ) from err
        except FreeboxAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(str(err)) from err
        except FreeboxError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        await self.async_request_refresh()
