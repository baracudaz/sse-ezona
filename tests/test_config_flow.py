"""Tests for the SSE eZóna config flow."""

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.sse_ezona.const import DOMAIN

USER_INPUT = {CONF_USERNAME: "Someone@Example.com", CONF_PASSWORD: "hunter2"}


async def _start_and_submit(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await _start_and_submit(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Someone@Example.com"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "someone@example.com"


async def test_same_account_twice_is_rejected(hass: HomeAssistant) -> None:
    await _start_and_submit(hass)
    result = await _start_and_submit(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
