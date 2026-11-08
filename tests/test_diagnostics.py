"""Tests for the diagnostics dump."""

import json

from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import MockConfigEntry

from custom_components.sse_ezona.const import CONF_DELIVERY_POINTS, CONF_ENERGY_AID
from custom_components.sse_ezona.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .common import POINT_SINGLE_RATE, POINT_TWO_RATE, FakeApi


async def test_diagnostics_hide_identifying_data(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_DELIVERY_POINTS: [POINT_TWO_RATE, POINT_SINGLE_RATE],
            CONF_ENERGY_AID: {POINT_TWO_RATE: "off", POINT_SINGLE_RATE: "on"},
        },
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await async_get_config_entry_diagnostics(hass, config_entry)
    dump = json.dumps(result, default=str)

    for secret in ("someone@example.com", "hunter2", "24ZSS", "Dom", "Chata", "T0000"):
        assert secret not in dump
    assert result["delivery_points"]["delivery_point_1"]["tariff"] == "DD5"
    assert (
        result["delivery_points"]["delivery_point_1"]["prices"]["VT"]["value"] == 0.25
    )
    # The aid choices stay, in delivery point order, without the IDs.
    assert result["options"] == {CONF_ENERGY_AID: ["off", "on"]}
    assert result["delivery_points"]["delivery_point_1"]["energy_aid_eligible"] is False
