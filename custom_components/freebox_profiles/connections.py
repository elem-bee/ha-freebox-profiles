"""Detect devices of a profile that connect, and notify about it."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_DEVICE_NAME,
    ATTR_MAC,
    ATTR_PROFILE_ID,
    ATTR_PROFILE_NAME,
    CONF_NOTIFY_PROFILES,
    CONF_NOTIFY_SERVICES,
    CONF_OFFLINE_DELAY,
    DEFAULT_OFFLINE_DELAY,
    DOMAIN,
    EVENT_DEVICE_CONNECTED,
)

_LOGGER = logging.getLogger(__name__)

NOTIFY_DOMAIN = "notify"

MESSAGES = {
    "en": "{device} is connected",
    "fr": "{device} est connecté",
}


def host_name(host: dict[str, Any]) -> str:
    """Return the best name Freebox OS knows for a host."""
    return (
        host.get("primary_name")
        or host.get("default_name")
        or host.get("l2ident", {}).get("id", "")
    )


def host_mac(host: dict[str, Any]) -> str | None:
    """Return the MAC address of a host."""
    return host.get("l2ident", {}).get("id")


@dataclass
class _HostState:
    reachable: bool
    offline_since: float


class ConnectionTracker:
    """Find, between two polls, the devices of a profile that connected.

    A device counts as connected when it becomes reachable after being
    unreachable for at least the configured delay: phones going to sleep
    for a moment do not trigger anything. The first poll only records the
    current state.
    """

    def __init__(self, delay_fn: Callable[[], float]) -> None:
        """Initialize; delay_fn returns the minimum offline time in seconds."""
        self._delay_fn = delay_fn
        self._hosts: dict[tuple[int, str], _HostState] = {}
        self._started = False

    def update(
        self, profiles: dict[int, dict[str, Any]]
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        """Return the (profile, host) pairs of the devices that connected."""
        now = time.monotonic()
        delay = self._delay_fn()
        connected: list[tuple[dict[str, Any], dict[str, Any]]] = []
        seen: set[tuple[int, str]] = set()

        for profile_id, profile in profiles.items():
            for host in profile.get("hosts") or []:
                mac = host_mac(host)
                if not mac:
                    continue
                key = (profile_id, mac)
                seen.add(key)
                reachable = bool(host.get("reachable"))
                state = self._hosts.get(key)
                if state is None:
                    # First poll, or device just added to the profile.
                    self._hosts[key] = _HostState(reachable, now)
                    continue
                if reachable and not state.reachable:
                    if self._started and now - state.offline_since >= delay:
                        connected.append((profile, host))
                elif not reachable and state.reachable:
                    state.offline_since = now
                state.reachable = reachable

        # Forget devices removed from their profile.
        for key in set(self._hosts) - seen:
            del self._hosts[key]
        self._started = True
        return connected


def signal_connected(entry: ConfigEntry) -> str:
    """Dispatcher signal sent for each device that connects."""
    return f"{DOMAIN}_{entry.entry_id}_device_connected"


@callback
def async_announce_connections(
    hass: HomeAssistant,
    entry: ConfigEntry,
    connected: list[tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    """Fire an event and send the notifications for each connected device."""
    services: list[str] = entry.options.get(CONF_NOTIFY_SERVICES, [])
    profiles_filter: list[str] = entry.options.get(CONF_NOTIFY_PROFILES, [])
    template = MESSAGES.get(hass.config.language.split("-")[0], MESSAGES["en"])

    for profile, host in connected:
        profile_id = int(profile["profile_id"])
        profile_name = str(profile.get("profile_name") or profile_id)
        device = host_name(host)
        mac = host_mac(host)
        event_data = {
            ATTR_PROFILE_ID: profile_id,
            ATTR_PROFILE_NAME: profile_name,
            ATTR_DEVICE_NAME: device,
            ATTR_MAC: mac,
        }
        hass.bus.async_fire(EVENT_DEVICE_CONNECTED, event_data)
        async_dispatcher_send(hass, signal_connected(entry), event_data)
        if profiles_filter and str(profile_id) not in profiles_filter:
            continue
        payload = {
            "title": profile_name,
            "message": template.format(device=device),
            "data": {"tag": f"{DOMAIN}_{mac}", "group": DOMAIN},
        }
        for service in services:
            hass.async_create_task(
                _async_notify(hass, service, payload),
                f"{DOMAIN} notification",
                eager_start=True,
            )


async def _async_notify(
    hass: HomeAssistant, service: str, payload: dict[str, Any]
) -> None:
    """Call one notify service, logging failures instead of raising."""
    if not hass.services.has_service(NOTIFY_DOMAIN, service):
        _LOGGER.warning(
            "Notification service notify.%s not found, check the options of "
            "Freebox Profiles",
            service,
        )
        return
    try:
        await hass.services.async_call(NOTIFY_DOMAIN, service, payload, blocking=True)
    except HomeAssistantError as err:
        _LOGGER.warning("Notification through notify.%s failed: %s", service, err)


def offline_delay_seconds(entry: ConfigEntry) -> float:
    """Return the minimum offline time before a connection is announced."""
    return float(entry.options.get(CONF_OFFLINE_DELAY, DEFAULT_OFFLINE_DELAY)) * 60
