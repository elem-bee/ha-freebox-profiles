"""Base entity for Freebox Profiles."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreeboxProfilesCoordinator


class FreeboxProfileEntity(CoordinatorEntity[FreeboxProfilesCoordinator]):
    """An entity attached to one Freebox profile (one device per profile)."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: FreeboxProfilesCoordinator, profile_id: int, key: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._profile_id = profile_id
        box_id = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        self._attr_unique_id = f"{box_id}_{profile_id}_{key}"
        name = str(self.profile.get("profile_name") or "").strip()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{box_id}_{profile_id}")},
            name=name or f"Profile {profile_id}",
            manufacturer="Free",
            model="Freebox OS profile",
            configuration_url=f"https://{coordinator.config_entry.data[CONF_HOST]}",
        )

    @property
    def profile(self) -> dict[str, Any]:
        """Return the current data of the profile."""
        return self.coordinator.data.get(self._profile_id, {})

    @property
    def available(self) -> bool:
        """Return True if the profile still exists."""
        return super().available and self._profile_id in self.coordinator.data


def async_track_new_profiles(
    coordinator: FreeboxProfilesCoordinator,
    async_add_entities: Callable[[Iterable[Entity]], None],
    factory: Callable[[int], Iterable[Entity]],
) -> Callable[[], None]:
    """Add entities for existing profiles, then for profiles created later."""
    known: set[int] = set()

    @callback
    def _add_new() -> None:
        new_ids = set(coordinator.data) - known
        if not new_ids:
            return
        known.update(new_ids)
        entities: list[Entity] = []
        for profile_id in sorted(new_ids):
            entities.extend(factory(profile_id))
        async_add_entities(entities)

    _add_new()
    return coordinator.async_add_listener(_add_new)
