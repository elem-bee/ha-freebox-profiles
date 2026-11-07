"""Config flow for Freebox Profiles."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL

from .api import (
    FreeboxClient,
    FreeboxConnectionError,
    FreeboxError,
    FreeboxUnsupportedError,
    create_ssl_context,
)
from .const import (
    APP_DEVICE_NAME,
    AUTH_POLL_INTERVAL,
    AUTH_POLL_MAX_TRIES,
    CONF_APP_TOKEN,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

RESULT_GRANTED = "granted"


class FreeboxProfilesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Freebox Profiles."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._host: str = DEFAULT_HOST
        self._port: int = DEFAULT_PORT
        self._verify_ssl: bool = True
        self._title: str = "Freebox"
        self._session: aiohttp.ClientSession | None = None
        self._client: FreeboxClient | None = None
        self._auth_task: asyncio.Task[str] | None = None
        self._auth_result: str | None = None

    # Helpers -----------------------------------------------------------------

    async def _async_connect(self) -> dict[str, Any]:
        """Open a client and read the Freebox information."""
        await self._async_close()
        ssl_context = await self.hass.async_add_executor_job(
            create_ssl_context, self._verify_ssl
        )
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl_context)
        )
        self._client = FreeboxClient(self._session, self._host, self._port)
        return await self._client.async_discover()

    async def _async_close(self) -> None:
        if self._session is not None:
            await self._session.close()
        self._session = None

    def async_remove(self) -> None:
        """Clean up when the flow is removed."""
        if self._auth_task is not None and not self._auth_task.done():
            self._auth_task.cancel()
        if self._session is not None:
            self.hass.async_create_task(self._async_close())

    async def _async_wait_for_authorization(self) -> str:
        """Request a token and wait until the user answers on the Freebox."""
        assert self._client is not None
        try:
            track_id = await self._client.async_request_authorization(APP_DEVICE_NAME)
            for _ in range(AUTH_POLL_MAX_TRIES):
                status = await self._client.async_authorization_status(track_id)
                if status != "pending":
                    return status
                await asyncio.sleep(AUTH_POLL_INTERVAL)
        except FreeboxError as err:
            _LOGGER.warning("Freebox authorization failed: %s", err)
            return "error"
        return "timeout"

    # Steps -------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the address of the Freebox."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            self._verify_ssl = user_input[CONF_VERIFY_SSL]
            try:
                info = await self._async_connect()
            except FreeboxUnsupportedError:
                errors["base"] = "unsupported"
            except FreeboxConnectionError:
                errors["base"] = "cannot_connect"
            except FreeboxError:
                _LOGGER.exception("Unexpected answer from the Freebox")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info.get("uid"))
                self._abort_if_unique_id_configured()
                self._title = (
                    info.get("box_model_name") or info.get("device_name") or "Freebox"
                )
                return await self.async_step_authorize()
            await self._async_close()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._host): str,
                vol.Required(CONF_PORT, default=self._port): vol.Coerce(int),
                vol.Required(CONF_VERIFY_SSL, default=self._verify_ssl): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for the user to accept the request on the Freebox."""
        if self._auth_task is None:
            self._auth_task = self.hass.async_create_task(
                self._async_wait_for_authorization()
            )
        if not self._auth_task.done():
            return self.async_show_progress(
                step_id="authorize",
                progress_action="wait_for_authorization",
                progress_task=self._auth_task,
            )
        self._auth_result = self._auth_task.result()
        self._auth_task = None
        if self._auth_result == RESULT_GRANTED:
            return self.async_show_progress_done(next_step_id="finish")
        return self.async_show_progress_done(next_step_id="authorization_failed")

    async def async_step_authorization_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort after a refused or expired authorization."""
        await self._async_close()
        reason = {
            "denied": "authorization_denied",
            "timeout": "authorization_timeout",
        }.get(self._auth_result or "", "authorization_error")
        return self.async_abort(reason=reason)

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create or update the config entry."""
        assert self._client is not None
        data = {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            CONF_VERIFY_SSL: self._verify_ssl,
            CONF_APP_TOKEN: self._client.app_token,
        }
        await self._async_close()
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )
        return self.async_create_entry(title=self._title, data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start again the authorization when the token was revoked."""
        self._host = entry_data[CONF_HOST]
        self._port = entry_data[CONF_PORT]
        self._verify_ssl = entry_data.get(CONF_VERIFY_SSL, True)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm before asking a new authorization on the Freebox."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await self._async_connect()
            except FreeboxConnectionError:
                errors["base"] = "cannot_connect"
            except FreeboxError:
                _LOGGER.exception("Unexpected answer from the Freebox")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info.get("uid"))
                self._abort_if_unique_id_mismatch(reason="wrong_box")
                return await self.async_step_authorize()
            await self._async_close()
        return self.async_show_form(step_id="reauth_confirm", errors=errors)
