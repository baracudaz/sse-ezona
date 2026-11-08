"""Sensors for SSE eZóna: prices and billing data per delivery point."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SseEzonaConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL, PRICE_BANDS
from .coordinator import DeliveryPoint, SseEzonaCoordinator

CURRENCY = "EUR"
PRICE_UNIT = "EUR/kWh"


@dataclass(frozen=True, kw_only=True)
class PointSensorDescription(SensorEntityDescription):
    """A sensor of one delivery point."""

    value_fn: Callable[[DeliveryPoint], float | str | date | None]
    attrs_fn: Callable[[DeliveryPoint], dict[str, Any]] | None = None


def _money(key: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "key": key,
        "translation_key": key,
        "device_class": SensorDeviceClass.MONETARY,
        "native_unit_of_measurement": CURRENCY,
        "suggested_display_precision": 2,
        **kwargs,
    }


def _invoice_attrs(point: DeliveryPoint) -> dict[str, Any]:
    invoice = point.invoice
    return {
        "issue_date": invoice.issue_date if invoice else None,
        "period_from": invoice.period_from if invoice else None,
        "period_to": invoice.period_to if invoice else None,
        "paid": invoice.paid if invoice else None,
    }


POINT_SENSORS: tuple[PointSensorDescription, ...] = (
    # The fixed monthly payment (supply fee and distribution access tariff)
    # incl. VAT, from the latest invoice.
    PointSensorDescription(
        **_money("monthly_fee"),
        value_fn=lambda p: p.invoice.monthly_fee if p.invoice else None,
    ),
    PointSensorDescription(
        **_money("owed_amount"),
        value_fn=lambda p: p.owed_amount,
    ),
    PointSensorDescription(
        **_money("advance_payment"),
        value_fn=lambda p: p.advance_payment,
        attrs_fn=lambda p: {"frequency": p.advance_frequency},
    ),
    PointSensorDescription(
        key="tariff",
        translation_key="tariff",
        value_fn=lambda p: p.tariff,
        attrs_fn=lambda p: {"product": p.product},
    ),
    PointSensorDescription(
        **_money("last_invoice_total"),
        value_fn=lambda p: p.invoice.total if p.invoice else None,
        attrs_fn=_invoice_attrs,
    ),
    PointSensorDescription(
        **_money("last_invoice_balance"),
        value_fn=lambda p: p.invoice.balance if p.invoice else None,
        attrs_fn=_invoice_attrs,
    ),
    PointSensorDescription(
        key="last_invoice_due_date",
        translation_key="last_invoice_due_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda p: p.invoice.due_date if p.invoice else None,
    ),
)


def _price_description(band: str) -> PointSensorDescription:
    def value(point: DeliveryPoint) -> float | None:
        price = point.prices.get(band)
        return price.value if price else None

    def attrs(point: DeliveryPoint) -> dict[str, Any]:
        price = point.prices.get(band)
        if price is None:
            return dict.fromkeys(
                ("valid_from", "supply_price", "regulated_price", "vat_rate")
            )
        return {
            "valid_from": price.valid_from.isoformat() if price.valid_from else None,
            "supply_price": round(price.supply, 4),
            "regulated_price": round(price.regulated, 4),
            "vat_rate": price.vat_rate,
        }

    return PointSensorDescription(
        key=f"price_{band.lower()}",
        translation_key=f"price_{band.lower()}",
        native_unit_of_measurement=PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=value,
        attrs_fn=attrs,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SseEzonaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors for every delivery point and the account."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for point in coordinator.data.delivery_points.values():
        # The contract decides the bands: VT and NT, or JT for single rate.
        bands = [band for band in PRICE_BANDS if band in point.supply_prices]
        descriptions = [_price_description(band) for band in bands]
        entities.extend(
            PointSensor(coordinator, point, description)
            for description in (*descriptions, *POINT_SENSORS)
        )
    async_add_entities(entities)


class PointSensor(CoordinatorEntity[SseEzonaCoordinator], SensorEntity):
    """A sensor of one delivery point."""

    _attr_has_entity_name = True
    entity_description: PointSensorDescription

    def __init__(
        self,
        coordinator: SseEzonaCoordinator,
        point: DeliveryPoint,
        description: PointSensorDescription,
    ) -> None:
        """Bind the sensor to a delivery point."""
        super().__init__(coordinator)
        self.entity_description = description
        self._point_id = point.id
        self._attr_unique_id = f"{point.id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, point.id)},
            name=point.name or f"SSE {point.eic or point.id}",
            manufacturer=MANUFACTURER,
            model=MODEL,
            model_id=point.tariff,
            serial_number=point.eic,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _point(self) -> DeliveryPoint | None:
        return self.coordinator.data.delivery_points.get(self._point_id)

    @property
    def available(self) -> bool:
        """Unavailable if the point disappeared from the account."""
        return super().available and self._point is not None

    @property
    def native_value(self) -> float | str | date | None:
        """Return the value from the latest fetch."""
        point = self._point
        return self.entity_description.value_fn(point) if point else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra details, e.g. when a price took effect."""
        point = self._point
        if point is None or self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(point)
