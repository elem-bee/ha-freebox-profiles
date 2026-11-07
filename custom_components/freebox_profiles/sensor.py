"""Sensors of a Freebox profile."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import MODE_ALLOWED, MODE_DENIED, MODE_WEBONLY
from .coordinator import FreeboxProfilesConfigEntry, FreeboxProfilesCoordinator
from .entity import FreeboxProfileEntity, async_track_new_profiles

PARALLEL_UPDATES = 0

ACCESS_MODES = [MODE_ALLOWED, MODE_DENIED, MODE_WEBONLY]


def _enum(value: Any) -> str | None:
    return value if value in ACCESS_MODES else None


def _override_end(profile: dict[str, Any]) -> datetime | None:
    """End of the override, None when there is none or it has no limit."""
    until = profile.get("override_until") or 0
    if not profile.get("override") or until <= 0:
        return None
    return dt_util.utc_from_timestamp(until)


def _next_change(profile: dict[str, Any]) -> datetime | None:
    """Next planned change; Freebox OS may keep a date in the past."""
    timestamp = profile.get("next_change") or 0
    if timestamp <= dt_util.utcnow().timestamp():
        return None
    return dt_util.utc_from_timestamp(timestamp)


def _device_name(host: dict[str, Any]) -> str:
    return (
        host.get("primary_name")
        or host.get("default_name")
        or host.get("l2ident", {}).get("id", "")
    )


def _connected(profile: dict[str, Any]) -> list[dict[str, Any]]:
    return [host for host in profile.get("hosts", []) if host.get("reachable")]


def _devices_attributes(profile: dict[str, Any]) -> dict[str, Any]:
    devices = []
    for host in profile.get("hosts", []):
        access_point = host.get("access_point") or {}
        wifi = access_point.get("wifi_information") or {}
        devices.append(
            {
                "name": _device_name(host),
                "mac": host.get("l2ident", {}).get("id"),
                "connected": bool(host.get("reachable")),
                "type": host.get("host_type"),
                "connection": access_point.get("connectivity_type"),
                "access_point": access_point.get("type"),
                "band": wifi.get("band"),
                "signal": wifi.get("signal"),
            }
        )
    return {"devices": devices}


@dataclass(frozen=True, kw_only=True)
class FreeboxProfileSensorDescription(SensorEntityDescription):
    """Describe a profile sensor."""

    value_fn: Callable[[dict[str, Any]], Any]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSORS: tuple[FreeboxProfileSensorDescription, ...] = (
    FreeboxProfileSensorDescription(
        key="current_mode",
        translation_key="current_mode",
        device_class=SensorDeviceClass.ENUM,
        options=ACCESS_MODES,
        value_fn=lambda profile: _enum(profile.get("current_mode")),
    ),
    FreeboxProfileSensorDescription(
        key="planned_mode",
        translation_key="planned_mode",
        device_class=SensorDeviceClass.ENUM,
        options=ACCESS_MODES,
        value_fn=lambda profile: _enum(profile.get("rule_mode")),
    ),
    FreeboxProfileSensorDescription(
        key="override_end",
        translation_key="override_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_override_end,
    ),
    FreeboxProfileSensorDescription(
        key="next_change",
        translation_key="next_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_change,
    ),
    FreeboxProfileSensorDescription(
        key="connected_devices",
        translation_key="connected_devices",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda profile: len(_connected(profile)),
        attributes_fn=_devices_attributes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxProfilesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of each profile."""
    coordinator = entry.runtime_data
    entry.async_on_unload(
        async_track_new_profiles(
            coordinator,
            async_add_entities,
            lambda profile_id: [
                FreeboxProfileSensor(coordinator, profile_id, description)
                for description in SENSORS
            ],
        )
    )


class FreeboxProfileSensor(FreeboxProfileEntity, SensorEntity):
    """A sensor of a Freebox profile."""

    entity_description: FreeboxProfileSensorDescription

    def __init__(
        self,
        coordinator: FreeboxProfilesCoordinator,
        profile_id: int,
        description: FreeboxProfileSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, profile_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.profile)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device list for the connected devices sensor."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.profile)
