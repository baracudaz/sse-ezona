"""Tests for subtracting the targeted energy aid from the prices."""

import logging

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.sse_ezona.const import (
    CONF_DELIVERY_POINTS,
    CONF_ENERGY_AID,
    CONF_ENERGY_AID_AMOUNT,
    DOMAIN,
)
from custom_components.sse_ezona.coordinator import parse_energy_aid

from .common import POINT_SINGLE_RATE, POINT_TWO_RATE, FakeApi

# 31.24 €/MWh excl. VAT at 19 % VAT, in €/kWh.
AID_2026 = 31.24 * 1.19 / 1000


def _state(hass: HomeAssistant, unique_id: str):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id, unique_id
    return hass.states.get(entity_id)


def _eligible(fake_api: FakeApi, point_id: str, value: bool = True) -> None:
    fake_api.details[point_id]["general"]["stateGrant"]["available"]["value"] = value


@pytest.fixture(autouse=True)
def in_2026(freezer: FrozenDateTimeFactory) -> None:
    """Prices are checked in a year with a known aid."""
    freezer.move_to("2026-06-15 10:00:00+02:00")


async def test_aid_applies_to_eligible_points(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """eZóna's eligibility flag lowers the price of that point only."""
    _eligible(fake_api, POINT_TWO_RATE)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    vt = _state(hass, f"{POINT_TWO_RATE}_price_vt")
    assert float(vt.state) == round(0.25 - AID_2026, 6)
    assert vt.attributes["energy_aid"] == 31.24
    assert vt.attributes["price_without_aid"] == 0.25
    assert vt.attributes["energy_aid_eligible"] is True
    assert vt.attributes["energy_aid_classified_on"] == "2026-09-01"
    assert float(_state(hass, f"{POINT_TWO_RATE}_price_nt").state) == round(
        0.2 - AID_2026, 6
    )

    jt = _state(hass, f"{POINT_SINGLE_RATE}_price_jt")
    assert float(jt.state) == 0.3
    assert jt.attributes["energy_aid"] == 0.0
    assert jt.attributes["energy_aid_eligible"] is False


async def test_aid_matches_a_real_invoice() -> None:
    """The formula reproduces the billed price of a 2026 invoice.

    VT end price without aid 0.2873865 €/kWh in eZóna; the invoice PDF
    billed 0.2502109 €/kWh.
    """
    assert round(0.2873865 - AID_2026, 7) == 0.2502109


async def test_no_aid_in_a_year_without_an_amount(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_api: FakeApi,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An eligible point gets no aid when the year's amount isn't known."""
    freezer.move_to("2027-01-10 10:00:00+01:00")
    _eligible(fake_api, POINT_TWO_RATE)
    with caplog.at_level(logging.WARNING):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    vt = _state(hass, f"{POINT_TWO_RATE}_price_vt")
    assert float(vt.state) == 0.25
    assert vt.attributes["energy_aid"] == 0.0
    assert "amount for 2027 isn't known" in caplog.text


async def test_options_override_eligibility_and_amount(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """The user can switch the aid on or off and set its amount."""
    _eligible(fake_api, POINT_TWO_RATE)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_DELIVERY_POINTS: [POINT_TWO_RATE, POINT_SINGLE_RATE],
            CONF_ENERGY_AID: {POINT_TWO_RATE: "off", POINT_SINGLE_RATE: "on"},
            CONF_ENERGY_AID_AMOUNT: 10.0,
        },
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert float(_state(hass, f"{POINT_TWO_RATE}_price_vt").state) == 0.25
    jt = _state(hass, f"{POINT_SINGLE_RATE}_price_jt")
    assert float(jt.state) == round(0.3 - 10 * 1.19 / 1000, 6)
    assert jt.attributes["energy_aid"] == 10.0


async def test_options_flow_sets_the_aid(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """The second options step sets the aid per point and the amount."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DELIVERY_POINTS: [POINT_TWO_RATE, POINT_SINGLE_RATE]}
    )
    assert result["step_id"] == "energy_aid"
    fields = {str(key): key for key in result["data_schema"].schema}
    assert list(fields) == [
        "Dom (24ZSS0000000001A)",
        "Chata (24ZSS0000000002B)",
        "advanced",
    ]
    assert fields["Dom (24ZSS0000000001A)"].default() == "auto"
    # Collapsed while there is no override.
    assert result["data_schema"].schema[fields["advanced"]].options["collapsed"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "Dom (24ZSS0000000001A)": "on",
            "Chata (24ZSS0000000002B)": "auto",
            "advanced": {CONF_ENERGY_AID_AMOUNT: 20},
        },
    )
    await hass.async_block_till_done()

    assert config_entry.options == {
        CONF_DELIVERY_POINTS: [POINT_TWO_RATE, POINT_SINGLE_RATE],
        CONF_ENERGY_AID: {POINT_TWO_RATE: "on", POINT_SINGLE_RATE: "auto"},
        CONF_ENERGY_AID_AMOUNT: 20.0,
    }
    # Reloaded with the new options.
    assert float(_state(hass, f"{POINT_TWO_RATE}_price_vt").state) == round(
        0.25 - 20 * 1.19 / 1000, 6
    )


async def test_emptied_amount_removes_the_override(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """An override is shown open and goes away when the field is emptied."""
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ENERGY_AID_AMOUNT: 20.0}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DELIVERY_POINTS: [POINT_TWO_RATE]}
    )
    fields = {str(key): key for key in result["data_schema"].schema}
    assert not result["data_schema"].schema[fields["advanced"]].options["collapsed"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"advanced": {}}
    )
    await hass.async_block_till_done()

    assert CONF_ENERGY_AID_AMOUNT not in config_entry.options


@pytest.mark.parametrize(
    ("detail", "expected"),
    [
        ({}, (None, None)),
        ({"general": {}}, (None, None)),
        ({"general": {"stateGrant": {"available": {"value": False}}}}, (False, None)),
        (
            {
                "general": {
                    "stateGrant": {
                        "available": {"value": True},
                        "validTill": {"value": "nonsense"},
                    }
                }
            },
            (True, None),
        ),
    ],
)
def test_parse_energy_aid_tolerates_missing_data(detail, expected) -> None:
    assert parse_energy_aid(detail) == expected
