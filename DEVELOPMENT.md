# Development

Developer documentation for the SSE eZóna Home Assistant integration. User documentation is in Slovak in [README.md](README.md).

## Prerequisites

- Python 3.14+
- Docker and Docker Compose
- Home Assistant itself isn't needed: `make install` puts the version pinned in `requirements.txt` into `.venv`

## Setup

```bash
# Clone the repository
git clone https://github.com/baracudaz/sse-ezona.git
cd sse-ezona

# Create a .venv and install dependencies (needed for make test/lint/format below)
make install

# Start a Home Assistant container on http://localhost:8124 with this integration mounted
make docker-up

# View logs
make docker-logs
```

The container uses the `stable` Home Assistant image. `make docker-restart` keeps the image that is already downloaded; to move to a new Home Assistant release, run `docker compose pull homeassistant && docker compose up -d homeassistant`.

Home Assistant keeps its state in `.data/config`. On a fresh checkout Docker Desktop can't create the mount point for `config/configuration.yaml` inside it, so `make docker-up` creates `.data/config/configuration.yaml` first. If you run `docker compose up` directly, run `mkdir -p .data/config && touch .data/config/configuration.yaml` before it.

## Tests and linting

```bash
make test           # run all tests
make test-coverage  # with coverage report
make check          # ruff format --check + ruff check (what CI runs)
make dev            # format, lint and test
```

The test harness is `pytest-homeassistant`, which Home Assistant core publishes with the same version as `homeassistant`; bump both together in `requirements.txt`.

## Portal API

Found by inspecting the eZóna web app; there is no public documentation.

- API base `https://ezona-zds.sse.sk/sse-gw/api/public/`, header `Authorization: Bearer <token>`.
- Login: `/sse-gw/auth/api/public/login/v1/{start,authenticate,wait,...}`. The token is opaque, valid about 2 hours, with no refresh token.
- The portal allows one session per account; logging in from Home Assistant may log the user out of the browser.

| Endpoint | Purpose |
|----------|---------|
| `user/v1/info` | Delivery points |
| `delivery-point/v1/{id}/delivery-point-info` | Tariff, advance payment, owed amount |
| `invoice/v1/balance?commodityType=ELECTRICITY` | Outstanding amount and overpayment |
| `invoice/v1?periodFrom=&periodTo=&commodityType=` | Invoices and advance schedules |
| `invoice/v1/{invoiceId}` | Invoice detail, including `endPrices` and the cost breakdown |

For 2026 invoices, `endPrices` can be the price *without* the targeted energy aid (31.24 €/MWh excl. VAT lower for eligible households), while the invoice PDF shows the billed price with aid.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

User-facing changes must update the Slovak user documentation in `README.md`. Release notes go into `CHANGELOG.md` (in English) under `## Version X.Y.Z`, together with the `version` bump in `custom_components/sse_ezona/manifest.json`.
