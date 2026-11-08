"""Constants for the SSE eZóna integration."""

from datetime import timedelta

DOMAIN = "sse_ezona"

# Option: IDs of the delivery points to create devices for.
CONF_DELIVERY_POINTS = "delivery_points"

MANUFACTURER = "Stredoslovenská energetika, a.s."
MODEL = "Odberné miesto elektriny"

COMMODITY_ELECTRICITY = "ELECTRICITY"

# Prices and billing data change rarely, and every fetch logs in, which can
# log the user out of eZóna in the browser. Once a day is enough.
UPDATE_INTERVAL = timedelta(hours=24)

# Settlement invoices are issued yearly, so look back a little over a year to
# always see the latest one. The gateway accepts this range for invoices.
INVOICE_LOOKBACK = timedelta(days=400)
# Earlier windows to try when a point has no settlement in the latest one,
# e.g. after a longer billing period.
INVOICE_LOOKBACK_WINDOWS = 3

# Used when an invoice doesn't give a usable VAT ratio.
DEFAULT_VAT_RATE = 0.19

# Price bands as eZóna names them: high tariff, low tariff, single rate.
PRICE_BANDS = ("VT", "NT", "JT")
MONTHLY_FEE_PRICE_NAME = "Mesačná platba"

STORAGE_VERSION = 1
