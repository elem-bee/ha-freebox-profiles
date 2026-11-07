"""Event entity: a device of a Freebox profile connected."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .connections import signal_connected
from .const import (
    ATTR_DEVICE_NAME,
    ATTR_MAC,
    ATTR_PROFILE_ID,
    EVENT_TYPE_CONNECTED,
)
from .coordinator import FreeboxProfilesConfigEntry, FreeboxProfilesCoordinator
from .entity import FreeboxProfileEntity, async_track_new_profiles

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxProfilesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the connection event of each profile."""
    coordinator = entry.runtime_data
    entry.async_on_unload(
        async_track_new_profiles(
            coordinator,
            async_add_entities,
            lambda profile_id: [FreeboxDeviceConnectedEvent(coordinator, profile_id)],
        )
    )


class FreeboxDeviceConnectedEvent(FreeboxProfileEntity, EventEntity):
    """Triggered each time a device of the profile connects."""

    _attr_translation_key = "device_connected"
    _attr_event_types = [EVENT_TYPE_CONNECTED]

    def __init__(
        self, coordinator: FreeboxProfilesCoordinator, profile_id: int
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, profile_id, "device_connected")

    async def async_added_to_hass(self) -> None:
        """Listen to the connections found by the coordinator."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_connected(self.coordinator.config_entry),
                self._async_device_connected,
            )
        )

    @callback
    def _async_device_connected(self, data: dict[str, Any]) -> None:
        if data[ATTR_PROFILE_ID] != self._profile_id:
            return
        self._trigger_event(
            EVENT_TYPE_CONNECTED,
            {ATTR_DEVICE_NAME: data[ATTR_DEVICE_NAME], ATTR_MAC: data[ATTR_MAC]},
        )
        self.async_write_ha_state()
