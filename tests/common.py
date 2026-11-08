"""Made-up portal responses and a fake API client for the tests.

The shapes follow real eZóna responses; every value is invented.
"""

from __future__ import annotations

import copy
from contextlib import asynccontextmanager
from typing import Any

POINT_TWO_RATE = "ELECTRICITY_24ZSS0000000001A"
POINT_SINGLE_RATE = "ELECTRICITY_24ZSS0000000002B"
INVOICE_TWO_RATE = "ELECTRICITY_SETTLEMENT_INVOICE_T000000000001"
INVOICE_SINGLE_RATE = "ELECTRICITY_SETTLEMENT_INVOICE_T000000000002"
INVOICE_OLD = "ELECTRICITY_SETTLEMENT_INVOICE_T000000000000"

USER_INFO = {
    "deliveryPoints": [
        {
            "id": POINT_TWO_RATE,
            "commodityType": "ELECTRICITY",
            "name": "Dom",
            "eic": "24ZSS0000000001A",
            "state": "ACTIVE",
        },
        {
            "id": POINT_SINGLE_RATE,
            "commodityType": "ELECTRICITY",
            "name": "Chata",
            "eic": "24ZSS0000000002B",
            "state": "ACTIVE",
        },
        {"id": "GAS_0000", "commodityType": "GAS", "name": "Plyn"},
    ],
}


def _detail(prices: list[tuple[str, float]], product: str) -> dict[str, Any]:
    return {
        "general": {
            "stateGrant": {
                "available": {"value": True},
                "validTill": {"value": "01.09.2026"},
            }
        },
        "merchant": {
            "productName": {"value": product},
            "price": [
                {
                    "value": value,
                    "currency": "EUR",
                    "remark1": f"{band}:",
                    "remark2": "/MWh",
                }
                for band, value in prices
            ],
        },
    }


DETAILS = {
    POINT_TWO_RATE: _detail([("VT", 150.0), ("NT", 140.0)], "DD5"),
    POINT_SINGLE_RATE: _detail([("JT", 160.0)], "DD1"),
}

POINT_INFO = {
    POINT_TWO_RATE: {
        "tariff": "DD5",
        "owedAmount": {"value": 0.0, "currency": "EUR"},
        "advancedPayment": {"amount": {"value": 80.0}, "frequency": "monthly"},
    },
    POINT_SINGLE_RATE: {
        "tariff": "DD1",
        "owedAmount": {"value": 12.5, "currency": "EUR"},
        "advancedPayment": {"amount": {"value": 20.0}, "frequency": "monthly"},
    },
}

BALANCE = {"outstanding": {"value": 12.5}, "excess": {"value": 0.0}}

INVOICES = {
    "invoices": [
        {
            "id": "ELECTRICITY_ADVANCES_BREAKDOWN_Z0",
            "type": "ELECTRICITY_ADVANCES_BREAKDOWN",
        },
        {
            "id": INVOICE_OLD,
            "type": "ELECTRICITY_SETTLEMENT_INVOICE",
            "issueDate": "2025-05-20",
        },
        {
            "id": INVOICE_TWO_RATE,
            "type": "ELECTRICITY_SETTLEMENT_INVOICE",
            "issueDate": "2026-05-29",
        },
        {
            "id": INVOICE_SINGLE_RATE,
            "type": "ELECTRICITY_SETTLEMENT_INVOICE",
            "issueDate": "2026-03-05",
        },
    ]
}


def _invoice(
    point_id: str,
    end_prices: list[tuple[str, float]],
    *,
    issue: str,
    balance: float,
    balance_type: str,
) -> dict[str, Any]:
    return {
        "dateFrom": "2025-05-17",
        "dateTo": "2026-05-20",
        "issueDate": issue,
        "dueDate": "2026-06-12",
        "paid": True,
        "amount": {
            "amountWithoutVat": 1000.0,
            "vat": 190.0,
            "amountWithVat": 1190.0,
            "balance": balance,
            "balanceType": balance_type,
        },
        "deliveryPoints": [
            {
                "id": point_id,
                "endPrices": [
                    {
                        "priceName": "Mesačná platba",
                        "priceValue": 12.9234,
                        "priceUnit": "EUR",
                    },
                    *(
                        {"priceName": band, "priceValue": value, "priceUnit": "EUR/kWh"}
                        for band, value in end_prices
                    ),
                ],
            }
        ],
    }


INVOICE_DETAILS = {
    INVOICE_TWO_RATE: _invoice(
        POINT_TWO_RATE,
        [("VT", 0.25), ("NT", 0.2)],
        issue="2026-05-29",
        balance=35.5,
        balance_type="OUTSTANDING_PAYMENTS",
    ),
    INVOICE_SINGLE_RATE: _invoice(
        POINT_SINGLE_RATE,
        [("JT", 0.3)],
        issue="2026-03-05",
        balance=41.0,
        balance_type="EXCESS_PAYMENTS",
    ),
    INVOICE_OLD: _invoice(
        POINT_TWO_RATE,
        [("VT", 0.1), ("NT", 0.1)],
        issue="2025-05-20",
        balance=1.0,
        balance_type="OUTSTANDING_PAYMENTS",
    ),
}


class FakeApi:
    """Stand-in for ``SseEzonaApi`` serving the data above."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Copy the data so a test can change it."""
        self.details = copy.deepcopy(DETAILS)
        self.invoice_details = copy.deepcopy(INVOICE_DETAILS)
        self.invoices = copy.deepcopy(INVOICES)
        self.invoice_windows: list[tuple[str, str]] = []
        self.fail: Exception | None = None
        self.invoice_requests: list[str] = []
        self.logins = 0

    @asynccontextmanager
    async def logged_in_session(self):
        if self.fail is not None:
            raise self.fail
        self.logins += 1
        yield self

    async def get_user_info(self) -> dict[str, Any]:
        return copy.deepcopy(USER_INFO)

    async def get_delivery_point(self, point_id: str) -> dict[str, Any]:
        return copy.deepcopy(self.details[point_id])

    async def get_delivery_point_info(self, point_id: str) -> dict[str, Any]:
        return copy.deepcopy(POINT_INFO[point_id])

    async def get_balance(self, commodity: str) -> dict[str, Any]:
        return copy.deepcopy(BALANCE)

    async def get_invoices(self, commodity: str, period_from: str, period_to: str):
        self.invoice_windows.append((period_from, period_to))
        listing = copy.deepcopy(self.invoices)
        listing["invoices"] = [
            item
            for item in listing["invoices"]
            if period_from <= item.get("issueDate", period_to) <= period_to
        ]
        return listing

    async def get_invoice(self, invoice_id: str) -> dict[str, Any]:
        self.invoice_requests.append(invoice_id)
        return copy.deepcopy(self.invoice_details[invoice_id])
