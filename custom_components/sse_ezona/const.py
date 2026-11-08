"""Constants for the SSE eZóna integration."""

from datetime import timedelta

DOMAIN = "sse_ezona"

# Option: IDs of the delivery points to create devices for.
CONF_DELIVERY_POINTS = "delivery_points"
# Option: per delivery point ID, whether the energy aid applies.
CONF_ENERGY_AID = "energy_aid"
ENERGY_AID_AUTO = "auto"  # as eZóna says (``stateGrant.available``)
ENERGY_AID_ON = "on"
ENERGY_AID_OFF = "off"
ENERGY_AID_MODES = (ENERGY_AID_AUTO, ENERGY_AID_ON, ENERGY_AID_OFF)
# Advanced option: the aid in €/MWh excl. VAT instead of the built-in amount.
CONF_ENERGY_AID_AMOUNT = "energy_aid_amount"

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

# The targeted energy aid (adresná energopomoc) lowers the supply price of
# eligible households by this much per year, in €/MWh excl. VAT, the same for
# every tariff. Act No. 260/2025 Coll. for 2026. A year missing here has no
# aid. eZóna's prices don't include it; its amount is in no response.
ENERGY_AID_EUR_PER_MWH = {2026: 31.24}

STORAGE_VERSION = 1
