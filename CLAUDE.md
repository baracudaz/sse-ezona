# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration (HACS) for the SSE customer portal eZóna (`https://ezona.sse.sk`): tariff prices and billing data for SSE electricity customers. All integration code lives in `custom_components/sse_ezona/`. Currently a scaffold: the config flow stores credentials, nothing talks to the portal yet.

It is a sibling of `baracudaz/ssd-ims` (the SSD distribution portal integration) and follows the same structure and tooling. SSE is a *supplier*; SSD/ZSD/VSD are *distributors* — they are independent, so this integration must not depend on `ssd_ims`. It exposes prices as entities; `ssd_ims` can read them through its price entity option (baracudaz/ssd-ims#33).

## Commands

```bash
make install   # create .venv and install requirements.txt (pins all dev/test deps)
make format    # ruff format .
make lint      # ruff check . --fix
make check     # format --check + lint, no auto-fix (what CI runs)
make test      # pytest tests/ -v --asyncio-mode=auto
make docker-up # Home Assistant in Docker on port 8124 (ssd-ims uses 8123)
```

`requirements.txt` is the single, pinned source of truth for dev/test dependencies; there is no `pyproject.toml`.

## Portal API (from browser inspection)

- API base `https://ezona-zds.sse.sk/sse-gw/api/public/`, header `Authorization: Bearer <token>`.
- Login: `/sse-gw/auth/api/public/login/v1/{start,authenticate,wait,...}`. The token is opaque, valid ~2 h, no refresh token — log in fresh for each daily fetch.
- Endpoints: `user/v1/info` (delivery points), `delivery-point/v1/{id}/delivery-point-info` (tariff, advance payment, owed amount), `invoice/v1/balance?commodityType=ELECTRICITY`, `invoice/v1?periodFrom=&periodTo=&commodityType=` (invoices and advance schedules), `invoice/v1/{invoiceId}` (detail incl. `endPrices` and cost breakdown).
- Gotcha: for 2026 invoices, `endPrices` can be the price *without* the targeted energy aid (31.24 €/MWh excl. VAT lower for eligible households), while the invoice PDF shows the billed price with aid.
- The portal allows one session per account; logging in from Home Assistant may log the user out of the browser.

## Conventions

- Python 3.14+ for development (pinned `homeassistant`); ruff for lint/format.
- Diagnostics must redact credentials, delivery point IDs, EIC, variable symbols, names and addresses.
- Fetch at most once a day — prices and billing data change rarely.
- `CHANGELOG.md` is maintained by hand per release under `## Version X.Y.Z` with bolded change-type prefixes (`**New feature**`, `**Bug fix**`, `**Internal**`, `**Docs**`, `**Maintenance**`). Bump `manifest.json` `"version"` alongside.
