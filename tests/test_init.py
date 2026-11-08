"""Tests for setting up the integration and the sensors it creates."""

from datetime import timedelta

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.sse_ezona.api import SseEzonaAuthError, SseEzonaConnectionError
from custom_components.sse_ezona.const import CONF_DELIVERY_POINTS, DOMAIN

from .common import POINT_SINGLE_RATE, POINT_TWO_RATE, FakeApi


def _state(hass: HomeAssistant, unique_id: str):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id, unique_id
    return hass.states.get(entity_id)


async def test_setup_creates_sensors(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """Every electricity point gets a device with prices and billing data."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    # Unchanged supply price: the end price is the invoice's.
    vt = _state(hass, f"{POINT_TWO_RATE}_price_vt")
    assert float(vt.state) == 0.25
    assert vt.attributes["unit_of_measurement"] == "EUR/kWh"
    assert vt.attributes["state_class"] == "measurement"
    assert "device_class" not in vt.attributes
    assert vt.attributes["valid_from"]
    assert vt.attributes["vat_rate"] == 0.19
    assert float(_state(hass, f"{POINT_TWO_RATE}_price_nt").state) == 0.2
    assert float(_state(hass, f"{POINT_SINGLE_RATE}_price_jt").state) == 0.3
    # Bands follow the contract.
    registry = er.async_get(hass)
    assert not registry.async_get_entity_id(
        "sensor", DOMAIN, f"{POINT_TWO_RATE}_price_jt"
    )
    assert not registry.async_get_entity_id(
        "sensor", DOMAIN, f"{POINT_SINGLE_RATE}_price_vt"
    )

    assert float(_state(hass, f"{POINT_TWO_RATE}_monthly_fee").state) == 12.9234
    assert _state(hass, f"{POINT_TWO_RATE}_tariff").state == "DD5"
    advance = _state(hass, f"{POINT_TWO_RATE}_advance_payment")
    assert float(advance.state) == 80.0
    assert advance.attributes["frequency"] == "monthly"
    assert float(_state(hass, f"{POINT_SINGLE_RATE}_owed_amount").state) == 12.5

    # The newest settlement of each point, not the older one.
    assert float(_state(hass, f"{POINT_TWO_RATE}_last_invoice_total").state) == 1190.0
    assert float(_state(hass, f"{POINT_TWO_RATE}_last_invoice_balance").state) == 35.5
    # An overpayment is negative.
    assert (
        float(_state(hass, f"{POINT_SINGLE_RATE}_last_invoice_balance").state) == -41.0
    )
    assert _state(hass, f"{POINT_TWO_RATE}_last_invoice_due_date").state == "2026-06-12"

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, POINT_TWO_RATE), config_entry.entry_id
    )
    assert device.name == "Dom"
    assert device.serial_number == "24ZSS0000000001A"
    assert device.model_id == "DD5"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_supply_price_change_updates_price(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """A new contract supply price shows up without a new invoice."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    before = _state(hass, f"{POINT_TWO_RATE}_price_vt")

    fake_api.details[POINT_TWO_RATE]["merchant"]["price"][0]["value"] = 160.0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1, minutes=1))
    await hass.async_block_till_done()

    after = _state(hass, f"{POINT_TWO_RATE}_price_vt")
    # +10 €/MWh excl. VAT is +0.0119 €/kWh incl. 19 % VAT.
    assert float(after.state) == 0.2619
    assert after.attributes["valid_from"] > before.attributes["valid_from"]
    # NT didn't change, and neither did when it took effect.
    nt = _state(hass, f"{POINT_TWO_RATE}_price_nt")
    assert float(nt.state) == 0.2
    # Invoice details are fetched once.
    assert (
        fake_api.invoice_requests.count("ELECTRICITY_SETTLEMENT_INVOICE_T000000000001")
        == 1
    )


async def test_prices_survive_a_restart(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """The regulated part and valid_from are kept across a reload."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    before = _state(hass, f"{POINT_TWO_RATE}_price_vt")
    await hass.config_entries.async_unload(config_entry.entry_id)

    fake_api.details[POINT_TWO_RATE]["merchant"]["price"][1]["value"] = 130.0
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    after = _state(hass, f"{POINT_TWO_RATE}_price_vt")
    assert after.state == before.state
    assert after.attributes["valid_from"] == before.attributes["valid_from"]
    assert float(_state(hass, f"{POINT_TWO_RATE}_price_nt").state) == 0.1881


async def test_rejected_credentials_start_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """A rejected login asks the user for a new password."""
    fake_api.fail = SseEzonaAuthError("HTTP 400")
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_unreachable_portal_retries(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """A connection problem retries the setup later."""
    fake_api.fail = SseEzonaConnectionError("TimeoutError")
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_only_selected_points_are_added(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """Unticking a point removes its device and sensors."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    devices = dr.async_get(hass)
    assert devices.async_get_device_by_identifier(
        (DOMAIN, POINT_SINGLE_RATE), config_entry.entry_id
    )

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_DELIVERY_POINTS: [POINT_TWO_RATE]}
    )
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert devices.async_get_device_by_identifier(
        (DOMAIN, POINT_TWO_RATE), config_entry.entry_id
    )
    assert not devices.async_get_device_by_identifier(
        (DOMAIN, POINT_SINGLE_RATE), config_entry.entry_id
    )
    assert not er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{POINT_SINGLE_RATE}_price_jt"
    )


async def test_options_change_the_selection(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_api: FakeApi
) -> None:
    """The options list the account's points and reload with the new choice."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    field = next(iter(result["data_schema"].schema))
    assert field.default() == [POINT_TWO_RATE, POINT_SINGLE_RATE]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DELIVERY_POINTS: [POINT_SINGLE_RATE]}
    )
    await hass.async_block_till_done()

    assert config_entry.options == {CONF_DELIVERY_POINTS: [POINT_SINGLE_RATE]}
    assert config_entry.state is ConfigEntryState.LOADED
    assert not er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{POINT_TWO_RATE}_price_vt"
    )
