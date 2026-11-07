"""Minimal asynchronous client for the Freebox OS API (profiles only).

This module only depends on aiohttp, so it can be tested outside Home Assistant.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import ssl
from typing import Any

import aiohttp

from .const import (
    APP_ID,
    APP_NAME,
    APP_VERSION,
    FREEBOX_ROOT_CA,
    MIN_API_MAJOR,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class FreeboxError(Exception):
    """Generic Freebox API error."""


class FreeboxConnectionError(FreeboxError):
    """The Freebox cannot be reached."""


class FreeboxUnsupportedError(FreeboxError):
    """The Freebox API version does not provide profiles."""


class FreeboxAuthError(FreeboxError):
    """The application token is missing, unknown or revoked."""


class FreeboxPermissionError(FreeboxError):
    """The application lacks the permission needed for this call."""


def create_ssl_context(verify_ssl: bool) -> ssl.SSLContext | bool:
    """Create the SSL context trusting the Freebox root CAs.

    Blocking (loads certificates): run it in an executor.
    """
    if not verify_ssl:
        return False
    return ssl.create_default_context(cadata=FREEBOX_ROOT_CA)


class FreeboxClient:
    """Talk to the Freebox OS API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        app_token: str | None = None,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._host = host
        self._port = port
        self._app_token = app_token
        self._base_url: str | None = None
        self._session_token: str | None = None
        self._permissions: dict[str, bool] = {}
        self._login_lock = asyncio.Lock()
        self.api_info: dict[str, Any] = {}

    @property
    def root_url(self) -> str:
        """Return the root URL of the Freebox."""
        return f"https://{self._host}:{self._port}"

    @property
    def app_token(self) -> str | None:
        """Return the application token."""
        return self._app_token

    @property
    def uid(self) -> str | None:
        """Return the unique id of the Freebox."""
        return self.api_info.get("uid")

    def has_permission(self, permission: str) -> bool:
        """Return True if the current session has the given permission."""
        return bool(self._permissions.get(permission))

    def invalidate_session(self) -> None:
        """Forget the session so that the next call logs in again."""
        self._session_token = None
        self._permissions = {}

    async def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Send a request and decode the JSON answer."""
        try:
            async with self._session.request(
                method, url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except ValueError as err:
                    raise FreeboxError(
                        f"Invalid answer from the Freebox (HTTP {resp.status})"
                    ) from err
                if not isinstance(data, dict):
                    raise FreeboxError("Unexpected answer from the Freebox")
                return resp.status, data
        except (aiohttp.ClientError, TimeoutError) as err:
            raise FreeboxConnectionError(
                f"Cannot reach the Freebox at {self.root_url}: {err}"
            ) from err

    async def async_discover(self) -> dict[str, Any]:
        """Read /api_version and compute the API base URL."""
        _, data = await self._request("GET", f"{self.root_url}/api_version")
        version = str(data.get("api_version", "0"))
        try:
            major = int(version.split(".", 1)[0])
        except ValueError as err:
            raise FreeboxUnsupportedError(f"Unknown API version {version}") from err
        if major < MIN_API_MAJOR:
            raise FreeboxUnsupportedError(
                f"API version {version} does not provide profiles (v{MIN_API_MAJOR}+ needed)"
            )
        base = data.get("api_base_url", "/api/")
        if not base.endswith("/"):
            base += "/"
        self._base_url = f"{self.root_url}{base}v{major}/"
        self.api_info = data
        return data

    async def _api(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        auth: bool = True,
        retry: bool = True,
    ) -> Any:
        """Call an API endpoint and return its result."""
        if self._base_url is None:
            await self.async_discover()
        headers: dict[str, str] = {}
        if auth:
            if self._session_token is None:
                await self.async_login()
            headers["X-Fbx-App-Auth"] = self._session_token or ""

        status, data = await self._request(
            method, f"{self._base_url}{path}", payload, headers
        )

        if data.get("success"):
            return data.get("result")

        code = data.get("error_code")
        if auth and retry and code in ("auth_required", "invalid_session"):
            # Session expired: log in again once.
            self.invalidate_session()
            return await self._api(method, path, payload, auth=auth, retry=False)
        if code == "insufficient_rights":
            raise FreeboxPermissionError(
                f"Missing Freebox permission: {data.get('missing_right', '?')}"
            )
        if status == 403 and auth:
            raise FreeboxAuthError(data.get("msg") or "Access denied")
        raise FreeboxError(f"{code}: {data.get('msg')}")

    async def async_login(self) -> None:
        """Open a session with the application token."""
        async with self._login_lock:
            if self._session_token is not None:
                return
            if not self._app_token:
                raise FreeboxAuthError("No application token")
            login = await self._api("GET", "login/", auth=False)
            challenge = login["challenge"]
            password = hmac.new(
                self._app_token.encode(), challenge.encode(), hashlib.sha1
            ).hexdigest()
            _, data = await self._request(
                "POST",
                f"{self._base_url}login/session/",
                {"app_id": APP_ID, "password": password},
            )
            if not data.get("success"):
                code = data.get("error_code")
                if code in ("invalid_token", "pending_token", "denied_from_external_ip"):
                    raise FreeboxAuthError(f"{code}: {data.get('msg')}")
                raise FreeboxError(f"{code}: {data.get('msg')}")
            result = data["result"]
            self._session_token = result["session_token"]
            self._permissions = result.get("permissions") or {}
            _LOGGER.debug("Freebox session opened, permissions: %s", self._permissions)

    # Authorization -----------------------------------------------------------

    async def async_request_authorization(self, device_name: str) -> int:
        """Ask the Freebox for a new application token.

        The user has to accept the request on the Freebox. Returns the track id.
        """
        result = await self._api(
            "POST",
            "login/authorize/",
            {
                "app_id": APP_ID,
                "app_name": APP_NAME,
                "app_version": APP_VERSION,
                "device_name": device_name,
            },
            auth=False,
        )
        self._app_token = result["app_token"]
        self.invalidate_session()
        return int(result["track_id"])

    async def async_authorization_status(self, track_id: int) -> str:
        """Return unknown, pending, timeout, granted or denied."""
        result = await self._api("GET", f"login/authorize/{track_id}", auth=False)
        return str(result.get("status", "unknown"))

    # Profiles ----------------------------------------------------------------

    async def async_get_profiles(self) -> list[dict[str, Any]]:
        """Return all profiles with their devices."""
        result = await self._api("GET", "network_control/")
        return list(result or [])

    async def async_update_profile(
        self, profile_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a profile (full object, as Freebox OS does)."""
        return await self._api("PUT", f"network_control/{profile_id}", payload)
