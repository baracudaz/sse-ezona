"""Tests for the billed consumption of the latest settlement period."""

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.sse_ezona.api import SseEzonaAuthError, SseEzonaConnectionError
from custom_components.sse_ezona.const import DOMAIN
from custom_components.sse_ezona.coordinator import parse_consumption

from .common import POINT_SINGLE_RATE, POINT_TWO_RATE, FakeApi


def _state(hass: HomeAssistant, unique_id: str):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id, unique_id
    return hass.states.get(entity_id)


async def test_billed_consumption_per_band(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """Each band shows the kWh of the latest period, with the period."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    vt = _state(hass, f"{POINT_TWO_RATE}_billed_consumption_vt")
    assert float(vt.state) == 1234.0
    assert vt.attributes["unit_of_measurement"] == "kWh"
    assert vt.attributes["device_class"] == "energy"
    # Not a meter: kept out of statistics and the energy dashboard.
    assert "state_class" not in vt.attributes
    assert str(vt.attributes["period_from"]) == "2025-05-17"
    assert str(vt.attributes["period_to"]) == "2026-05-20"
    assert (
        float(_state(hass, f"{POINT_TWO_RATE}_billed_consumption_nt").state) == 2500.0
    )

    jt = _state(hass, f"{POINT_SINGLE_RATE}_billed_consumption_jt")
    assert float(jt.state) == 842.0
    # Bands follow the contract, as for prices.
    assert not er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{POINT_SINGLE_RATE}_billed_consumption_vt"
    )


async def test_consumption_failure_keeps_the_rest(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """If only the consumption request fails, everything else still updates."""
    fake_api.consumption_fail = SseEzonaConnectionError("HTTP 500")
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    vt = _state(hass, f"{POINT_TWO_RATE}_billed_consumption_vt")
    assert vt.state == "unknown"
    assert vt.attributes["period_to"] is None
    assert float(_state(hass, f"{POINT_TWO_RATE}_price_vt").state) == 0.25


async def test_consumption_auth_error_still_fails(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """A rejected session isn't hidden by the fallback."""
    fake_api.consumption_fail = SseEzonaAuthError("HTTP 401")
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (None, None),
        ({}, None),
        ({"consumption": [{"periodTo": "2026-01-01"}]}, None),
        (
            {
                "consumption": [
                    {
                        "periodFrom": "2025-01-01",
                        "periodTo": "2026-01-01",
                        "electricity": {
                            "oneTariff": {"value": 950, "unit": "kWh"},
                            "highTariff": {"value": 1, "unit": "GWh"},
                            "lowTariff": {"value": "n/a", "unit": "MWh"},
                        },
                    }
                ]
            },
            ({"JT": 950.0}, None),
        ),
    ],
)
def test_parse_consumption_tolerates_odd_data(data, expected) -> None:
    result = parse_consumption(data)
    if expected is None:
        assert result is None
    else:
        assert (result.bands, result.total) == expected
