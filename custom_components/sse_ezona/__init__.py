"""The SSE eZóna integration: prices and billing data from the SSE portal."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SseEzonaApi
from .const import DOMAIN
from .coordinator import SseEzonaCoordinator

PLATFORMS = [Platform.SENSOR]

type SseEzonaConfigEntry = ConfigEntry[SseEzonaCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SseEzonaConfigEntry) -> bool:
    """Set up SSE eZóna from a config entry."""
    api = SseEzonaApi(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = SseEzonaCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    _remove_unselected_devices(hass, entry, set(coordinator.data.delivery_points))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SseEzonaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _remove_unselected_devices(
    hass: HomeAssistant, entry: SseEzonaConfigEntry, selected: set[str]
) -> None:
    """Remove devices of delivery points the user no longer wants.

    Also removes the account device of versions before the selection existed.
    """
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        point_ids = {value for domain, value in device.identifiers if domain == DOMAIN}
        if not point_ids & selected:
            registry.async_remove_device(device.id)
