"""Client for the SSE eZóna portal API.

The portal has no public API documentation; everything here mirrors what the
eZóna web app does. Login is an OAuth implicit flow driven by JSON calls:

1. ``login/v1/start`` returns a temporary access token and, for username and
   password accounts, a one-time ``secretPayload``.
2. ``login/v1/authenticate`` takes the credentials with that payload. On
   success it returns a ``redirectUri`` whose fragment carries
   ``access_token``, ``token_type``, ``expires_in`` and ``state``. If it
   returns another ``nextStep`` instead, the account needs a second factor,
   which isn't supported.

The portal allows one session per account, so the client revokes its token
when done (``access-token/v1/revoke``) to keep the user's browser session
disruption short.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import ssl
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qs, urlsplit

import aiohttp

_LOGGER = logging.getLogger(__name__)

GATEWAY_URL = "https://ezona-zds.sse.sk/sse-gw"
AUTH_URL = f"{GATEWAY_URL}/auth/api/public"
API_URL = f"{GATEWAY_URL}/api/public"
GATEWAY_URL_PATH = urlsplit(GATEWAY_URL).path

# Values the eZóna web app sends when starting a login.
CLIENT_ID = "sseWebPortal"
SCOPE = "CHANNEL_WEB AUTHTYPE_* PERM_* ROLE_*"
RESPONSE_TYPE = "token"
REDIRECT_URI = "/"

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
WEB_ORIGIN = "https://ezona.sse.sk"
USER_AGENT = "Mozilla/5.0"


def _loggable_path(url: str) -> str:
    """Return the URL path without IDs; IDs carry the EIC or invoice numbers.

    The query and body are left out too: they may hold personal data.
    """
    path = urlsplit(url).path.removeprefix(GATEWAY_URL_PATH)
    return re.sub(r"[^/]*\d{6,}[^/]*", "<id>", path)


def _create_ssl_context() -> ssl.SSLContext:
    """Return a TLS 1.2 context for the eZóna gateway.

    The gateway rejects the TLS 1.3 handshake of recent Python versions;
    TLS 1.2 works. Certificate and hostname verification stay on. Loading the
    CA store does file I/O, so call this in an executor.
    """
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    return context


class SseEzonaError(Exception):
    """Base error for the eZóna client."""


class SseEzonaConnectionError(SseEzonaError):
    """The portal couldn't be reached or answered unexpectedly."""


class SseEzonaGatewayRejectedError(SseEzonaConnectionError):
    """The portal's web application firewall answered with its rejection page."""


class SseEzonaAuthError(SseEzonaError):
    """The credentials were rejected or the session expired."""


class SseEzonaUnsupportedLoginError(SseEzonaError):
    """The account needs a login step this client doesn't support (e.g. 2FA)."""


class SseEzonaApi:
    """Minimal async client for the eZóna portal."""

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        """Store the HTTP session and credentials; nothing is sent yet."""
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None
        self._token_type = "Bearer"
        self._ssl_context: ssl.SSLContext | None = None

    @property
    def logged_in(self) -> bool:
        """Return whether the client holds an access token."""
        return self._token is not None

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "Accept": "application/json;charset=UTF-8",
            "Accept-Language": "sk",
            "Content-Type": "application/json",
            "Origin": WEB_ORIGIN,
            "Referer": f"{WEB_ORIGIN}/",
            "Requestid": uuid.uuid4().hex,
            "User-Agent": USER_AGENT,
        }

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        auth: bool = True,
    ) -> Any:
        if self._ssl_context is None:
            try:
                self._ssl_context = await asyncio.to_thread(_create_ssl_context)
            except (OSError, ssl.SSLError) as err:
                raise SseEzonaConnectionError(
                    f"Can't load the CA certificates: {err}"
                ) from err
        headers = self._headers()
        if auth:
            if self._token is None:
                raise SseEzonaAuthError("Not logged in")
            headers["Authorization"] = f"{self._token_type} {self._token}"
        try:
            async with self._session.request(
                method,
                url,
                json=json_body,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                ssl=self._ssl_context,
                allow_redirects=False,
            ) as resp:
                body = await resp.text()
                if resp.status >= 300:
                    _LOGGER.debug(
                        "%s %s answered HTTP %s",
                        method,
                        _loggable_path(url),
                        resp.status,
                    )
                # The firewall's rejection page comes with HTTP 200 (or 403) and
                # says nothing about the credentials, so check it first. Long
                # date ranges trigger it too.
                if (
                    "html" in resp.headers.get("Content-Type", "")
                    and "request rejected" in body[:2000].lower()
                ):
                    raise SseEzonaGatewayRejectedError(
                        "Request rejected by the gateway"
                    )
                if resp.status in (401, 403):
                    raise SseEzonaAuthError(f"HTTP {resp.status}")
                if resp.status == 400 and not auth:
                    # The login endpoints answer rejected credentials with 400.
                    raise SseEzonaAuthError("HTTP 400")
                if resp.status >= 300:
                    raise SseEzonaConnectionError(f"HTTP {resp.status}")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SseEzonaConnectionError(type(err).__name__) from err
        if not body:
            return None
        try:
            return json.loads(body)
        except ValueError as err:
            raise SseEzonaConnectionError("Response is not JSON") from err

    async def login(self) -> None:
        """Log in with username and password and store the access token."""
        state = secrets.token_hex(16)
        start = await self._request(
            "POST",
            f"{AUTH_URL}/login/v1/start",
            json_body={
                "clientId": CLIENT_ID,
                "redirectUri": REDIRECT_URI,
                "responseType": RESPONSE_TYPE,
                "scope": SCOPE,
                "state": state,
            },
            auth=False,
        )
        try:
            temporary_token = start["temporaryAccessToken"]
            secret_payload = start["nextStep"]["usernamePasswordMethod"][
                "secretPayload"
            ]
        except (KeyError, TypeError) as err:
            raise SseEzonaConnectionError("Unexpected login/start response") from err

        result = await self._request(
            "POST",
            f"{AUTH_URL}/login/v1/authenticate",
            json_body={
                "authToken": {
                    "usernamePasswordToken": {
                        "secretPayload": secret_payload,
                        "username": self._username,
                        "password": self._password,
                    }
                },
                "temporaryAccessToken": temporary_token,
            },
            auth=False,
        )
        if not isinstance(result, dict):
            raise SseEzonaConnectionError("Unexpected login/authenticate response")

        fragment = parse_qs(urlsplit(result.get("redirectUri") or "").fragment)
        token = fragment.get("access_token", [None])[0]
        if token is None:
            if result.get("nextStep"):
                raise SseEzonaUnsupportedLoginError(
                    "Login needs another step: " + ", ".join(result["nextStep"])
                )
            raise SseEzonaAuthError("No access token in login response")
        if fragment.get("state", [state])[0] != state:
            raise SseEzonaConnectionError("Login state mismatch")

        self._token = token
        self._token_type = fragment.get("token_type", ["Bearer"])[0]
        _LOGGER.debug(
            "Logged in, token valid for %s s", fragment.get("expires_in", ["?"])[0]
        )

    async def logout(self) -> None:
        """Revoke the access token; errors are logged and ignored."""
        if self._token is None:
            return
        token, self._token = self._token, None
        try:
            await self._request(
                "POST",
                f"{AUTH_URL}/access-token/v1/revoke",
                json_body={"token": token},
                auth=False,
            )
        except SseEzonaError as err:
            _LOGGER.debug("Token revoke failed: %s", err)

    @asynccontextmanager
    async def logged_in_session(self) -> AsyncIterator[SseEzonaApi]:
        """Log in for the duration of the block, then revoke the token."""
        await self.login()
        try:
            yield self
        finally:
            await self.logout()

    async def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        """GET an API path relative to ``/api/public/``."""
        return await self._request("GET", f"{API_URL}/{path}", params=params)

    async def get_user_info(self) -> dict[str, Any]:
        """Return the user info including ``deliveryPoints``."""
        return await self.get("user/v1/info")

    async def get_delivery_point(self, delivery_point_id: str) -> dict[str, Any]:
        """Return the delivery point detail incl. the contract supply price."""
        return await self.get(f"delivery-point/v1/{delivery_point_id}")

    async def get_delivery_point_info(self, delivery_point_id: str) -> dict[str, Any]:
        """Return tariff, advance payment and owed amount of a delivery point."""
        return await self.get(
            f"delivery-point/v1/{delivery_point_id}/delivery-point-info"
        )

    async def get_balance(self, commodity_type: str) -> dict[str, Any]:
        """Return the account balance for a commodity (e.g. ``ELECTRICITY``)."""
        return await self.get(
            "invoice/v1/balance", params={"commodityType": commodity_type}
        )

    async def get_invoices(
        self, commodity_type: str, period_from: str, period_to: str
    ) -> dict[str, Any]:
        """Return invoices issued between two ISO dates."""
        return await self.get(
            "invoice/v1",
            params={
                "periodFrom": period_from,
                "periodTo": period_to,
                "commodityType": commodity_type,
            },
        )

    async def get_invoice(self, invoice_id: str) -> dict[str, Any]:
        """Return the detail of one invoice."""
        return await self.get(f"invoice/v1/{invoice_id}")
