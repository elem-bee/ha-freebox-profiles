"""Diagnostics for Freebox Profiles (personal data redacted)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_APP_TOKEN
from .coordinator import FreeboxProfilesConfigEntry

TO_REDACT = {
    CONF_APP_TOKEN,
    "addr",
    "bssid",
    "domain_name",
    "id",
    "info",
    "l2ident",
    "mac",
    "macs",
    "names",
    "primary_name",
    "default_name",
    "profile_name",
    "name",
    "ssid",
    "uid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FreeboxProfilesConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    api_info = {
        key: coordinator.client.api_info.get(key)
        for key in ("api_version", "box_model", "box_model_name", "device_type")
    }
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "api": api_info,
        "profiles": async_redact_data(
            [profile for profile in coordinator.data.values()], TO_REDACT
        ),
    }
