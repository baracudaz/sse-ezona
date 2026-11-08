# Changelog

## Version 0.4.0

- **New feature**: Billed consumption VT/NT or JT (kWh) of the latest settlement period per delivery point, with the period as attributes, for comparing with meter register readings (#16)
- **Maintenance**: `make docker-up` works on a fresh checkout

## Version 0.3.0

- **New feature**: Prices include the 2026 targeted energy aid (31.24 €/MWh excl. VAT) for eligible delivery points. Eligibility comes from eZóna's `stateGrant.available` and can be set per point in the options; the amount can be overridden there too. New price attributes `energy_aid`, `price_without_aid`, `energy_aid_eligible` and `energy_aid_classified_on` (#18)
- **Maintenance**: Ruff 0.17, which formats Markdown too, skips the Copilot guide
- **Docs**: Slovak README explains the energy aid and the options

## Version 0.2.0

- **New feature**: Sensors per electricity delivery point: end prices VT/NT or JT (EUR/kWh incl. VAT, with `valid_from`), monthly fee, amount due, advance payment, tariff, and total, balance and due date of the latest settlement invoice (#1). Prices don't include the 2026 energy aid yet (#18)
- **New feature**: The config flow checks the credentials, lets you pick the delivery points to add, and asks for a new password when eZóna rejects the old one; the options change the selection
- **New feature**: Diagnostics without credentials, EIC, delivery point names or invoice numbers
- **New feature**: SSE icon and logo in Home Assistant (official logo from sse.sk, with dark-theme variants)
- **Docs**: Slovak README describes the sensors and how the end price is calculated

## Version 0.1.0

- **Internal**: Repository scaffold — config flow for eZóna credentials, CI (ruff, pytest, hassfest, HACS validation, CodeQL), development tooling. No portal access yet
