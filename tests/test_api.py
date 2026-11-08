"""Tests for the eZóna API client against mocked portal responses."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.sse_ezona.api import (
    API_URL,
    AUTH_URL,
    SseEzonaApi,
    SseEzonaAuthError,
    SseEzonaConnectionError,
    SseEzonaUnsupportedLoginError,
)

START_URL = f"{AUTH_URL}/login/v1/start"
AUTH_ENDPOINT = f"{AUTH_URL}/login/v1/authenticate"
REVOKE_URL = f"{AUTH_URL}/access-token/v1/revoke"

START_RESPONSE = {
    "temporaryAccessToken": "temp-token",
    "nextStep": {"usernamePasswordMethod": {"secretPayload": "secret"}},
}


def _authenticate_response(state: str, token: str = "access-token") -> dict:
    return {
        "redirectUri": (
            f"/#access_token={token}&token_type=Bearer&expires_in=7200&state={state}"
        )
    }


class _LoginRecorder:
    """Mock start/authenticate, echoing the login state into the token fragment."""

    def __init__(self, aioclient_mock: AiohttpClientMocker) -> None:
        self.state: str | None = None
        self.auth_body: dict | None = None
        aioclient_mock.post(START_URL, side_effect=self._start)
        aioclient_mock.post(AUTH_ENDPOINT, side_effect=self._authenticate)
        aioclient_mock.post(REVOKE_URL, status=204)

    async def _start(self, method, url, data):
        self.state = data["state"]
        return AiohttpClientMockResponse(method, url, json=START_RESPONSE)

    async def _authenticate(self, method, url, data):
        self.auth_body = data
        return AiohttpClientMockResponse(
            method, url, json=_authenticate_response(self.state)
        )


async def test_login_fetch_and_revoke(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A full session logs in, sends the bearer token and revokes it."""
    echo = _LoginRecorder(aioclient_mock)
    aioclient_mock.get(f"{API_URL}/user/v1/info", json={"deliveryPoints": []})

    api = SseEzonaApi(async_get_clientsession(hass), "user@example.com", "pw")
    async with api.logged_in_session():
        assert api.logged_in
        assert await api.get_user_info() == {"deliveryPoints": []}
    assert not api.logged_in

    assert echo.auth_body == {
        "authToken": {
            "usernamePasswordToken": {
                "secretPayload": "secret",
                "username": "user@example.com",
                "password": "pw",
            }
        },
        "temporaryAccessToken": "temp-token",
    }
    info_call = next(
        c for c in aioclient_mock.mock_calls if "user/v1/info" in str(c[1])
    )
    assert info_call[3]["Authorization"] == "Bearer access-token"
    revoke_call = next(c for c in aioclient_mock.mock_calls if str(c[1]) == REVOKE_URL)
    assert revoke_call[2] == {"token": "access-token"}


async def test_rejected_credentials(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 400 from authenticate means wrong credentials."""
    aioclient_mock.post(START_URL, json=START_RESPONSE)
    aioclient_mock.post(AUTH_ENDPOINT, status=400, json={"errors": []})

    api = SseEzonaApi(async_get_clientsession(hass), "user@example.com", "bad")
    with pytest.raises(SseEzonaAuthError):
        await api.login()


async def test_second_factor_is_unsupported(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Another nextStep instead of a token means the account needs 2FA."""
    aioclient_mock.post(START_URL, json=START_RESPONSE)
    aioclient_mock.post(
        AUTH_ENDPOINT, json={"nextStep": {"smsOtpMethod": {"secretPayload": "x"}}}
    )

    api = SseEzonaApi(async_get_clientsession(hass), "user@example.com", "pw")
    with pytest.raises(SseEzonaUnsupportedLoginError):
        await api.login()


async def test_state_mismatch(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A token for a different login state is rejected."""
    aioclient_mock.post(START_URL, json=START_RESPONSE)
    aioclient_mock.post(AUTH_ENDPOINT, json=_authenticate_response("other-state"))

    api = SseEzonaApi(async_get_clientsession(hass), "user@example.com", "pw")
    with pytest.raises(SseEzonaConnectionError):
        await api.login()
    assert not api.logged_in


async def test_expired_session(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 401 from a data endpoint is an auth error."""
    _LoginRecorder(aioclient_mock)
    aioclient_mock.get(f"{API_URL}/invoice/v1/balance", status=401)

    api = SseEzonaApi(async_get_clientsession(hass), "user@example.com", "pw")
    await api.login()
    with pytest.raises(SseEzonaAuthError):
        await api.get_balance("ELECTRICITY")
