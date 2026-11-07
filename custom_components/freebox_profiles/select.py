"""Select entity: mode of a Freebox profile (planning, allowed, denied)."""

from __future__ import annotations

import time

import voluptuous as vol

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_DURATION,
    ATTR_MODE,
    MODE_ALLOWED,
    MODE_DENIED,
    MODE_PLANNING,
    SERVICE_CLEAR_OVERRIDE,
    SERVICE_SET_OVERRIDE,
)
from .coordinator import FreeboxProfilesConfigEntry
from .entity import FreeboxProfileEntity, async_track_new_profiles

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxProfilesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the mode select of each profile."""
    coordinator = entry.runtime_data

    entry.async_on_unload(
        async_track_new_profiles(
            coordinator,
            async_add_entities,
            lambda profile_id: [FreeboxProfileModeSelect(coordinator, profile_id)],
        )
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_OVERRIDE,
        {
            vol.Required(ATTR_MODE): vol.In([MODE_ALLOWED, MODE_DENIED]),
            vol.Optional(ATTR_DURATION, default=0): vol.All(
                cv.positive_int, vol.Range(max=60 * 24 * 365)
            ),
        },
        "async_set_override",
    )
    platform.async_register_entity_service(
        SERVICE_CLEAR_OVERRIDE, None, "async_clear_override"
    )


class FreeboxProfileModeSelect(FreeboxProfileEntity, SelectEntity):
    """Choose between the planning and a manual override."""

    _attr_translation_key = "mode"
    _attr_options = [MODE_PLANNING, MODE_ALLOWED, MODE_DENIED]

    def __init__(self, coordinator, profile_id: int) -> None:
        """Initialize the select."""
        super().__init__(coordinator, profile_id, "mode")

    @property
    def current_option(self) -> str | None:
        """Return planning when no override is active."""
        if not self.profile.get("override"):
            return MODE_PLANNING
        mode = self.profile.get("override_mode")
        return mode if mode in (MODE_ALLOWED, MODE_DENIED) else None

    async def async_select_option(self, option: str) -> None:
        """Apply the chosen mode, without time limit."""
        if option == MODE_PLANNING:
            await self.async_clear_override()
        else:
            await self.async_set_override(option, 0)

    async def async_set_override(self, mode: str, duration: int = 0) -> None:
        """Allow or block the profile, for duration minutes (0 = no limit)."""
        until = int(time.time()) + duration * 60 if duration else 0
        await self.coordinator.async_set_override(
            self._profile_id, True, mode, until
        )

    async def async_clear_override(self) -> None:
        """Return the profile to its planning."""
        await self.coordinator.async_set_override(self._profile_id, False)
