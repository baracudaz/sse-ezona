# Changelog

## Version 0.2.0

- **New feature**: Sensors per electricity delivery point: end prices VT/NT or JT (EUR/kWh incl. VAT, with `valid_from`), monthly fee, amount due, advance payment, tariff, and total, balance and due date of the latest settlement invoice (#1). Prices don't include the 2026 energy aid yet (#18)
- **New feature**: The config flow checks the credentials, lets you pick the delivery points to add, and asks for a new password when eZóna rejects the old one; the options change the selection
- **New feature**: Diagnostics without credentials, EIC, delivery point names or invoice numbers
- **New feature**: SSE icon and logo in Home Assistant (official logo from sse.sk, with dark-theme variants)
- **Docs**: Slovak README describes the sensors and how the end price is calculated

## Version 0.1.0

- **Internal**: Repository scaffold — config flow for eZóna credentials, CI (ruff, pytest, hassfest, HACS validation, CodeQL), development tooling. No portal access yet
