"""The Freebox Profiles integration."""

from __future__ import annotations

import aiohttp

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant

from .api import FreeboxClient, create_ssl_context
from .const import CONF_APP_TOKEN
from .coordinator import FreeboxProfilesConfigEntry, FreeboxProfilesCoordinator

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: FreeboxProfilesConfigEntry
) -> bool:
    """Set up Freebox Profiles from a config entry."""
    ssl_context = await hass.async_add_executor_job(
        create_ssl_context, entry.data.get(CONF_VERIFY_SSL, True)
    )
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context))
    client = FreeboxClient(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_APP_TOKEN],
    )
    coordinator = FreeboxProfilesCoordinator(hass, entry, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await session.close()
        raise

    entry.runtime_data = coordinator
    entry.async_on_unload(session.close)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FreeboxProfilesConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
