"""The SSE eZóna integration.

Scaffold only: setting up an entry stores the credentials but doesn't talk
to the portal yet. See the repository's issues for the planned API client,
coordinator and sensors.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SSE eZóna from a config entry."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
