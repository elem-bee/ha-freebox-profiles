"""Switch entity: pause a Freebox profile (block Internet, no time limit)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODE_DENIED
from .coordinator import FreeboxProfilesConfigEntry
from .entity import FreeboxProfileEntity, async_track_new_profiles

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxProfilesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the pause switch of each profile."""
    coordinator = entry.runtime_data

    entry.async_on_unload(
        async_track_new_profiles(
            coordinator,
            async_add_entities,
            lambda profile_id: [FreeboxProfilePauseSwitch(coordinator, profile_id)],
        )
    )


class FreeboxProfilePauseSwitch(FreeboxProfileEntity, SwitchEntity):
    """On: Internet blocked for the profile. Off: the profile follows its planning.

    Same as the "Pause" button of the Freebox app.
    """

    _attr_translation_key = "pause"

    def __init__(self, coordinator, profile_id: int) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, profile_id, "pause")

    @property
    def is_on(self) -> bool:
        """Return True when the profile is paused by an override."""
        return bool(self.profile.get("override")) and (
            self.profile.get("override_mode") == MODE_DENIED
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Pause the profile, without time limit."""
        await self.coordinator.async_set_override(
            self._profile_id, True, MODE_DENIED, 0
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """End the pause: the profile follows its planning again.

        An "allowed" override is left untouched.
        """
        if self.is_on:
            await self.coordinator.async_set_override(self._profile_id, False)
