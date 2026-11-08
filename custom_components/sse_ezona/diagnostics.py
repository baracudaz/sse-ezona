"""Diagnostics for SSE eZóna.

Delivery point IDs contain the EIC, and names often hold an address, so
points are listed under opaque labels and only non-identifying values are
included. Amounts and prices stay: they are what a bug report is about.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import SseEzonaConfigEntry

TO_REDACT = [CONF_USERNAME, CONF_PASSWORD]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SseEzonaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    points: dict[str, Any] = {}
    for i, point in enumerate(data.delivery_points.values() if data else ()):
        invoice = asdict(point.invoice) if point.invoice else None
        if invoice:
            invoice.pop("id")
        points[f"delivery_point_{i + 1}"] = {
            "tariff": point.tariff,
            "product": point.product,
            "owed_amount": point.owed_amount,
            "advance_payment": point.advance_payment,
            "advance_frequency": point.advance_frequency,
            "supply_prices": point.supply_prices,
            "invoice": invoice,
            "prices": {
                band: {k: v for k, v in asdict(price).items() if k != "invoice_id"}
                for band, price in point.prices.items()
            },
        }
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "delivery_points_available": len(data.available) if data else None,
        "delivery_points": points,
    }
