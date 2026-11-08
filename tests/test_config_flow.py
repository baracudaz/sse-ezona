"""Tests for the SSE eZóna config flow."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry

from custom_components.sse_ezona.api import (
    SseEzonaAuthError,
    SseEzonaConnectionError,
    SseEzonaUnsupportedLoginError,
)
from custom_components.sse_ezona.const import CONF_DELIVERY_POINTS, DOMAIN

from .common import POINT_SINGLE_RATE, POINT_TWO_RATE, USER_INFO, FakeApi

USER_INPUT = {CONF_USERNAME: "Someone@Example.com", CONF_PASSWORD: "hunter2"}


@pytest.fixture
def flow_api() -> Iterator[FakeApi]:
    """Replace the client the config flow uses for the login check."""
    api = FakeApi()
    with (
        patch("custom_components.sse_ezona.config_flow.SseEzonaApi", return_value=api),
        patch("custom_components.sse_ezona.async_setup_entry", return_value=True),
    ):
        yield api


async def _start_and_submit(hass: HomeAssistant, user_input=USER_INPUT):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def _pick(hass: HomeAssistant, result, points: list[str]):
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "delivery_points"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DELIVERY_POINTS: points}
    )


async def test_user_flow_creates_entry(hass: HomeAssistant, flow_api: FakeApi) -> None:
    result = await _start_and_submit(hass)
    # Only electricity points are offered, all ticked.
    schema = result["data_schema"].schema
    field = next(iter(schema))
    assert field.default() == [POINT_TWO_RATE, POINT_SINGLE_RATE]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DELIVERY_POINTS: []}
    )
    assert result["errors"] == {"base": "no_selection"}

    result = await _pick(hass, result, [POINT_SINGLE_RATE])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Someone@Example.com"
    assert result["data"] == USER_INPUT
    assert result["options"] == {CONF_DELIVERY_POINTS: [POINT_SINGLE_RATE]}
    assert result["result"].unique_id == "someone@example.com"
    assert flow_api.logins == 1


async def test_single_point_skips_the_choice(
    hass: HomeAssistant, flow_api: FakeApi
) -> None:
    info = {"deliveryPoints": USER_INFO["deliveryPoints"][:1]}
    with patch.object(flow_api, "get_user_info", return_value=info):
        result = await _start_and_submit(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_DELIVERY_POINTS: [POINT_TWO_RATE]}


async def test_account_without_electricity(
    hass: HomeAssistant, flow_api: FakeApi
) -> None:
    info = {"deliveryPoints": USER_INFO["deliveryPoints"][2:]}
    with patch.object(flow_api, "get_user_info", return_value=info):
        result = await _start_and_submit(hass)

    assert result["errors"] == {"base": "no_delivery_points"}


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (SseEzonaAuthError("HTTP 400"), "invalid_auth"),
        (SseEzonaUnsupportedLoginError("smsOtpMethod"), "unsupported_login"),
        (SseEzonaConnectionError("TimeoutError"), "cannot_connect"),
    ],
)
async def test_login_errors_are_shown(
    hass: HomeAssistant, flow_api: FakeApi, error: Exception, key: str
) -> None:
    flow_api.fail = error
    result = await _start_and_submit(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": key}

    # Fixing the problem lets the same flow go on.
    flow_api.fail = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["step_id"] == "delivery_points"


async def test_same_account_twice_is_rejected(
    hass: HomeAssistant, flow_api: FakeApi
) -> None:
    await _pick(hass, await _start_and_submit(hass), [POINT_TWO_RATE])
    result = await _start_and_submit(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_password(hass: HomeAssistant, flow_api: FakeApi) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "someone@example.com", CONF_PASSWORD: "old"},
        unique_id="someone@example.com",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    flow_api.fail = SseEzonaAuthError("HTTP 400")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "still-wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    flow_api.fail = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new"
