"""Fetch and combine eZóna data once a day.

Prices
------
eZóna has no field with the current end price. It has two halves of it:

- the delivery point's contract *supply* price per band (``merchant.price``,
  €/MWh excl. VAT), which is current but excludes distribution and the
  regulated charges, and
- the end prices on the latest settlement invoice (``endPrices``, €/kWh incl.
  VAT), which are complete but only as current as that invoice.

So the end price is rebuilt as ``(supply − aid + regulated) × (1 + VAT)``,
where the regulated part (distribution, losses, system charges, nuclear fund)
is ``endPrice / (1 + VAT) − supply`` taken when a new invoice is first seen
and stored. A later supply price change then shows up the next day, while the
regulated part follows with the next invoice.

Neither half includes the targeted energy aid, which lowers the supply price
of eligible households (``ENERGY_AID_EUR_PER_MWH``). eZóna says whether a point
is eligible (``general.stateGrant.available``) but not by how much, so the
amount comes from the built-in table, and the user can override both.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    SseEzonaApi,
    SseEzonaAuthError,
    SseEzonaError,
    SseEzonaUnsupportedLoginError,
)
from .const import (
    COMMODITY_ELECTRICITY,
    CONF_DELIVERY_POINTS,
    CONF_ENERGY_AID,
    CONF_ENERGY_AID_AMOUNT,
    DEFAULT_VAT_RATE,
    DOMAIN,
    ENERGY_AID_AUTO,
    ENERGY_AID_EUR_PER_MWH,
    ENERGY_AID_ON,
    INVOICE_LOOKBACK,
    INVOICE_LOOKBACK_WINDOWS,
    MONTHLY_FEE_PRICE_NAME,
    PRICE_BANDS,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PRICE_DECIMALS = 6


@dataclass
class Invoice:
    """A settlement invoice of one delivery point."""

    id: str
    issue_date: date | None
    due_date: date | None
    period_from: date | None
    period_to: date | None
    total: float | None
    balance: float | None
    paid: bool | None
    vat_rate: float
    end_prices: dict[str, float]
    monthly_fee: float | None


@dataclass
class Price:
    """The end price of one band, incl. VAT."""

    value: float
    # When the price took effect; ``None`` until a change has been observed.
    valid_from: datetime | None
    supply: float
    regulated: float
    vat_rate: float
    invoice_id: str | None
    # The energy aid subtracted, €/MWh excl. VAT; 0 without aid.
    energy_aid: float = 0.0
    # The end price before the aid, incl. VAT.
    value_without_aid: float | None = None


@dataclass
class DeliveryPoint:
    """Data of one electricity delivery point."""

    id: str
    eic: str | None
    name: str | None
    tariff: str | None
    product: str | None
    owed_amount: float | None
    advance_payment: float | None
    advance_frequency: str | None
    supply_prices: dict[str, float] = field(default_factory=dict)
    # Whether eZóna lists the point as eligible for the energy aid; ``None``
    # if it doesn't say.
    energy_aid_eligible: bool | None = None
    # The date of that classification ("Adresná energopomoc podľa zaradenia
    # k"), not an expiry date.
    energy_aid_classified_on: date | None = None
    invoice: Invoice | None = None
    prices: dict[str, Price] = field(default_factory=dict)


@dataclass
class AccountData:
    """Everything fetched in one update."""

    # The selected delivery points with their data.
    delivery_points: dict[str, DeliveryPoint]
    # All electricity delivery points of the account, ID to label, for
    # changing the selection.
    available: dict[str, str]


def point_label(raw: dict[str, Any]) -> str:
    """Return how a delivery point from ``user/v1/info`` is shown to the user."""
    name, eic = raw.get("name"), raw.get("eic") or raw.get("id")
    return f"{name} ({eic})" if name else str(eic)


def electricity_points(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the electricity delivery points from ``user/v1/info``."""
    return [
        raw
        for raw in info.get("deliveryPoints") or []
        if raw.get("commodityType") == COMMODITY_ELECTRICITY and raw.get("id")
    ]


def _value(obj: Any, *path: str) -> Any:
    """Follow ``path`` through nested dicts; ``None`` if any step is missing."""
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    return dt_util.parse_date(value[:10])


def parse_supply_prices(detail: dict[str, Any]) -> dict[str, float]:
    """Return the contract supply price per band in €/MWh excl. VAT."""
    prices: dict[str, float] = {}
    for item in _value(detail, "merchant", "price") or []:
        band = str(item.get("remark1") or "").strip().rstrip(":").upper()
        value = _float(item.get("value"))
        if band in PRICE_BANDS and value is not None:
            prices[band] = value
    return prices


def parse_energy_aid(detail: dict[str, Any]) -> tuple[bool | None, date | None]:
    """Return eligibility for the energy aid and the classification date."""
    grant = _value(detail, "general", "stateGrant")
    if not isinstance(grant, dict):
        return None, None
    available = _value(grant, "available", "value")
    eligible = available if isinstance(available, bool) else None
    classified_on = None
    valid_till = _value(grant, "validTill", "value")
    if isinstance(valid_till, str):
        try:
            classified_on = datetime.strptime(valid_till.strip(), "%d.%m.%Y").date()
        except ValueError:
            classified_on = _date(valid_till)
    return eligible, classified_on


def energy_aid(
    point: DeliveryPoint, mode: str, year: int, amount: float | None
) -> float:
    """Return the aid for a point in €/MWh excl. VAT, 0 if it doesn't apply.

    ``mode`` is the user's choice: as eZóna says, or always on or off.
    ``amount`` overrides the built-in amount for ``year``.
    """
    if mode == ENERGY_AID_AUTO:
        applies = point.energy_aid_eligible is True
    else:
        applies = mode == ENERGY_AID_ON
    if not applies:
        return 0.0
    if amount is not None:
        return amount
    return ENERGY_AID_EUR_PER_MWH.get(year, 0.0)


def parse_invoice(invoice_id: str, detail: dict[str, Any], point_id: str) -> Invoice:
    """Return the parts of an invoice detail that concern one delivery point."""
    amount = detail.get("amount") or {}
    without_vat = _float(amount.get("amountWithoutVat"))
    vat = _float(amount.get("vat"))
    vat_rate = DEFAULT_VAT_RATE
    if without_vat and vat is not None:
        vat_rate = round(vat / without_vat, 2)

    balance = _float(amount.get("balance"))
    if balance is not None:
        # The amount is a magnitude; the type says which way it goes.
        balance = abs(balance)
        if amount.get("balanceType") == "EXCESS_PAYMENTS":
            balance = -balance

    total = _float(amount.get("amountWithVat"))
    points = detail.get("deliveryPoints") or []
    end_prices: dict[str, float] = {}
    monthly_fee = None
    for point in points:
        if point.get("id") != point_id:
            continue
        if len(points) > 1:
            # A shared invoice: the amounts above are for all its points.
            # Each point has its own amount excl. VAT; the balance after
            # advance payments exists only for the whole invoice.
            point_amount = _float(_value(point, "consumption", "amountWithoutVat"))
            total = (
                round(point_amount * (1 + vat_rate), 2)
                if point_amount is not None
                else None
            )
            balance = None
        for item in point.get("endPrices") or []:
            name = str(item.get("priceName") or "").strip()
            value = _float(item.get("priceValue"))
            if value is None:
                continue
            if name == MONTHLY_FEE_PRICE_NAME:
                monthly_fee = value
            elif name.upper() in PRICE_BANDS:
                end_prices[name.upper()] = value

    return Invoice(
        id=invoice_id,
        issue_date=_date(detail.get("issueDate")),
        due_date=_date(detail.get("dueDate")),
        period_from=_date(detail.get("dateFrom")),
        period_to=_date(detail.get("dateTo")),
        total=total,
        balance=balance,
        paid=detail.get("paid"),
        vat_rate=vat_rate,
        end_prices=end_prices,
        monthly_fee=monthly_fee,
    )


def compute_prices(
    point: DeliveryPoint, stored: dict[str, Any], now: datetime, aid: float = 0.0
) -> dict[str, Any]:
    """Set ``point.prices`` and return the updated stored state of the point.

    ``stored`` holds the regulated part per band with the invoice and VAT
    rate it was taken from, and the last published price per band with the
    time it took effect.

    The regulated part is ``endPrice / (1 + VAT) − supply``, using the supply
    price when the invoice is first seen. eZóna has no supply price as of the
    invoice date, so if the supply price changed between the invoice and the
    first time it is seen (e.g. on a fresh install), the regulated part
    absorbs that difference until the next invoice.

    ``aid`` (€/MWh excl. VAT) is subtracted from the supply price. Neither
    the invoice's end prices nor the supply price include it, so the
    regulated part doesn't depend on it.
    """
    stored = dict(stored)
    regulated: dict[str, float] = dict(stored.get("regulated") or {})
    invoice = point.invoice
    if invoice is not None and invoice.end_prices:
        if stored.get("invoice_id") != invoice.id:
            regulated = {}
            stored["invoice_id"] = invoice.id
        stored["vat_rate"] = invoice.vat_rate
        # Also fills bands whose supply price was missing on an earlier day.
        for band, end_price in invoice.end_prices.items():
            supply = point.supply_prices.get(band)
            if band not in regulated and supply is not None:
                regulated[band] = end_price * 1000 / (1 + invoice.vat_rate) - supply
        stored["regulated"] = regulated
    # Without a usable invoice, keep building on the stored regulated part.
    vat_rate = stored.get("vat_rate", DEFAULT_VAT_RATE)

    published: dict[str, Any] = dict(stored.get("prices") or {})
    point.prices = {}
    for band, regulated_part in regulated.items():
        supply = point.supply_prices.get(band)
        if supply is None:
            continue
        without_aid = round(
            (supply + regulated_part) * (1 + vat_rate) / 1000, PRICE_DECIMALS
        )
        value = round(
            (supply - aid + regulated_part) * (1 + vat_rate) / 1000, PRICE_DECIMALS
        )
        previous = published.get(band)
        if previous is None:
            # First sighting: when this price took effect is unknown.
            valid_from = None
        elif previous.get("value") != value:
            valid_from = now
        else:
            valid_from = dt_util.parse_datetime(previous.get("valid_from") or "")
        published[band] = {
            "value": value,
            "valid_from": valid_from.isoformat() if valid_from else None,
        }
        point.prices[band] = Price(
            value=value,
            valid_from=valid_from,
            supply=supply,
            regulated=regulated_part,
            vat_rate=vat_rate,
            invoice_id=stored.get("invoice_id"),
            energy_aid=aid,
            value_without_aid=without_aid,
        )
    stored["prices"] = published
    return stored


class SseEzonaCoordinator(DataUpdateCoordinator[AccountData]):
    """Log in once a day, fetch everything, log out."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: SseEzonaApi
    ) -> None:
        """Set up the coordinator for one eZóna account."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._stored: dict[str, Any] | None = None
        # Invoice details don't change once issued.
        self._invoice_cache: dict[str, dict[str, Any]] = {}

    async def _async_update_data(self) -> AccountData:
        if self._stored is None:
            self._stored = await self._store.async_load() or {}
        try:
            async with self.api.logged_in_session():
                data = await self._fetch()
        except (SseEzonaAuthError, SseEzonaUnsupportedLoginError) as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SseEzonaError as err:
            raise UpdateFailed(str(err)) from err

        now = dt_util.utcnow()
        options = self.config_entry.options
        modes: dict[str, str] = options.get(CONF_ENERGY_AID) or {}
        amount = options.get(CONF_ENERGY_AID_AMOUNT)
        # The aid is set per calendar year.
        year = dt_util.as_local(now).year
        points_state = self._stored.setdefault("delivery_points", {})
        for point in data.delivery_points.values():
            mode = modes.get(point.id, ENERGY_AID_AUTO)
            aid = energy_aid(point, mode, year, amount)
            if (
                mode == ENERGY_AID_AUTO
                and point.energy_aid_eligible
                and amount is None
                and year not in ENERGY_AID_EUR_PER_MWH
            ):
                _LOGGER.warning(
                    "A delivery point is eligible for the energy aid, but its "
                    "amount for %s isn't known; prices are without the aid. "
                    "Set the amount in the integration's options",
                    year,
                )
            points_state[point.id] = compute_prices(
                point, points_state.get(point.id, {}), now, aid
            )
        await self._store.async_save(self._stored)
        return data

    async def _fetch(self) -> AccountData:
        api = self.api
        info = await api.get_user_info()
        available = electricity_points(info)
        selected = self.config_entry.options.get(CONF_DELIVERY_POINTS)
        wanted = [raw for raw in available if selected is None or raw["id"] in selected]
        # One access token serves parallel requests, and the portal is slow.
        fetched = await asyncio.gather(
            *(
                asyncio.gather(
                    api.get_delivery_point(raw["id"]),
                    api.get_delivery_point_info(raw["id"]),
                )
                for raw in wanted
            )
        )
        points: dict[str, DeliveryPoint] = {}
        for raw, (detail, point_info) in zip(wanted, fetched, strict=True):
            point_id = raw["id"]
            points[point_id] = DeliveryPoint(
                id=point_id,
                eic=raw.get("eic"),
                name=raw.get("name"),
                tariff=point_info.get("tariff"),
                product=_value(detail, "merchant", "productName", "value"),
                owed_amount=_float(_value(point_info, "owedAmount", "value")),
                advance_payment=_float(
                    _value(point_info, "advancedPayment", "amount", "value")
                ),
                advance_frequency=_value(point_info, "advancedPayment", "frequency"),
                supply_prices=parse_supply_prices(detail),
            )
            (
                points[point_id].energy_aid_eligible,
                points[point_id].energy_aid_classified_on,
            ) = parse_energy_aid(detail)

        await self._attach_invoices(points)
        return AccountData(
            delivery_points=points,
            available={raw["id"]: point_label(raw) for raw in available},
        )

    async def _attach_invoices(self, points: dict[str, DeliveryPoint]) -> None:
        """Give each delivery point its latest settlement invoice.

        The gateway rejects long date ranges, so look back one window at a
        time and stop as soon as every point has an invoice.
        """
        missing = set(points)
        period_to = dt_util.now().date()
        for _ in range(INVOICE_LOOKBACK_WINDOWS):
            if not missing:
                return
            period_from = period_to - INVOICE_LOOKBACK
            listing = await self.api.get_invoices(
                COMMODITY_ELECTRICITY, period_from.isoformat(), period_to.isoformat()
            )
            settlements = [
                item
                for item in (listing or {}).get("invoices") or []
                if str(item.get("type", "")).endswith("SETTLEMENT_INVOICE")
                and item.get("id")
            ]
            # The listing doesn't say which delivery point an invoice is for;
            # the detail does. Walk from the newest.
            settlements.sort(key=lambda item: item.get("issueDate") or "", reverse=True)
            for item in settlements:
                if not missing:
                    return
                invoice_id = item["id"]
                detail = self._invoice_cache.get(invoice_id)
                if detail is None:
                    detail = await self.api.get_invoice(invoice_id)
                    self._invoice_cache[invoice_id] = detail
                for point_ref in detail.get("deliveryPoints") or []:
                    point_id = point_ref.get("id")
                    if point_id in missing:
                        points[point_id].invoice = parse_invoice(
                            invoice_id, detail, point_id
                        )
                        missing.discard(point_id)
            period_to = period_from - timedelta(days=1)
