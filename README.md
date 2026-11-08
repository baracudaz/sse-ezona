# SSE eZóna for Home Assistant

> **Work in progress** — this repository is a scaffold. The integration can be added and stores your credentials, but doesn't read anything from the portal yet.

A Home Assistant custom integration for the customer portal of Stredoslovenská energetika ([SSE eZóna](https://ezona.sse.sk)). It is meant for SSE electricity customers in any distribution region (SSD, ZSD or VSD).

## Planned features

Per delivery point:

- Current VT/NT price (EUR/kWh incl. VAT), or the single-rate price for single-tariff points
- Balance: amount to pay / overpayment
- Advance payment amount and frequency
- Supply tariff (e.g. `DD5`)
- Last invoice total and due date

The price sensors are meant to feed the cost statistics of the [SSD IMS integration](https://github.com/baracudaz/ssd-ims) (see baracudaz/ssd-ims#33), or any other energy setup in Home Assistant.

## Limitations

- Only accounts that sign in with username (e-mail) and password. Google, Facebook and Apple logins and accounts that require a one-time code (SMS/QR) aren't supported.
- The final prices eZóna reports may not include the 2026 targeted energy aid (*adresná energopomoc*). See the issues for details.

## Development

```bash
make install   # create .venv and install requirements.txt
make check     # ruff format --check + ruff check
make test      # pytest
make docker-up # Home Assistant in Docker on http://localhost:8124 with this integration mounted
```

## License

AGPL-3.0, see [LICENSE](LICENSE).
