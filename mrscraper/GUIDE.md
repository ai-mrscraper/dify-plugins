# Developing the MrScraper Dify Plugin

The plugin exposes seven tools: Status, Scrape HTML, Scrape Markdown, Get screenshot, Scrape brand, Scrape JSON, and Web search. `common/client.py` calls the MrScraper HTTPS API directly with `httpx`. See the [README](README.md) for user-facing parameters and examples.

## Environment

Use Python 3.12 and run commands from the `mrscraper` directory.

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

Keep runtime dependencies synchronized between `pyproject.toml` and `requirements.txt`, and update `uv.lock` when dependencies change. The `dify-plugin` and `httpx` versions are pinned for reproducible plugin installation.

## API contract

The contract mirrors the MrScraper Python SDK and CLI. Every request sends `Authorization: Bearer <token>`, `x-api-token: <token>`, `accept: application/json`, and `Content-Type: application/json`. The token is never placed in a URL. Booleans are serialized as `true`/`false`.

- **Status:** `GET https://api.app.mrscraper.com/api/v1/subscription-accounts`, 600-second deadline. Return the body unchanged.
- **Page services:** `GET https://api.mrscraper.com` with every field in the query string, in the documented order, and a deadline of `timeout + 30` seconds. Send only the parameters the Scraper API reference lists. Always send `url`, `timeout` (1–330, default 300), `saveResult=true` (fixed, not an input), and `maxAge` (0–604800000, default 0); send `waitForSelector` (up to 500 characters), `geoCode`, and `maxRetries` (at least 0) only when set. Never send `tokenCap`.
  - **Scrape HTML:** `html=true`, `markdown=false`, optional `browserRendering` (omitted for `auto`), `warmStart`, `blockResources`, optional `action`, and `screenshot` (`false`, `full`, `top`, or `WIDTHxHEIGHT` with an optional `-ZOOM`; default `false`). Any screenshot other than `false` also sends `browserRendering=true`, overriding the `browser_rendering` input.
  - **Scrape Markdown:** `markdown=true`, `html=false`, `screenshot=false`, optional `browserRendering`, `warmStart`, `blockResources`, and optional `action`.
  - **Get screenshot:** `screenshot=full`, `html=false`, `markdown=false`, and `browserRendering=true`, plus the shared page controls only. The API still returns the page HTML.
  - **Scrape JSON:** `prompt`, `agent=general`, `html` (default `true`), optional `browserRendering`, `warmStart`, `blockResources`, and a boolean `screenshot`. Above an 8,000-character encoded URL, switch to `POST` and move `url`, `prompt`, and `agent` to the JSON body.
- **Scrape brand:** `GET https://api.mrscraper.com?action=brand-scraping&url=...&bundle=none`, 120-second deadline.
- **Web search:** `GET https://api.mrscraper.com?action=websearch&query=...&numResults=..`, 120-second deadline. `country` is sent only when set; `numResults` is an integer from 10 to 100.
- A `401` response means the token is invalid.

## Adapter contract

- `provider/mrscraper.yaml` registers exactly the seven `mrscraper_*` tools, in the standard service order.
- The provider owns the `api_token` credential and validates it through Status. Credentials are never tool parameters.
- Tool YAML files define the Dify interface. Tool and parameter descriptions are copied verbatim from the MrScraper standard service reference; only names follow Dify's snake_case convention. `browser_rendering` is a select (`auto`, `true`, `false`) because Dify booleans cannot be left unset.
- `common/parameters.py` validates and normalizes every input before an HTTP request. Empty optional inputs take the standard defaults or stay omitted. `common/client.py` serializes the normalized values.
- Emit objects and arrays as Dify JSON messages, strings unchanged as text, binary data as blobs, and scalar values as text. HTTP status and response headers are omitted from tool content.
- Convert HTTP, network, and parameter errors into useful Dify errors without exposing the provider token.

## Verification

Automated tests replace `MrscraperClient.transport` with an in-memory `httpx.MockTransport`. Tests should establish that the seven registered schemas load and match the standard descriptions, inputs reach the correct endpoint with the correct method, query, and body, credentials stay at provider level, error messages do not expose secrets, and JSON/text outputs retain their native shape.

Run live checks only when explicitly requested, with a token supplied through the environment or Dify credentials. Never write tokens to files. Save live results under `test-results/`, which is ignored by Git and excluded from the package.

For a Dify development connection, copy `.env.example` to `.env`, configure the deployment's debug connection, then run:

```bash
uv run python -m main
```

Keep `.env` and tokens out of source control and packaged artifacts.

## Release consistency

Keep the plugin version consistent across `pyproject.toml` and `manifest.yaml`. Confirm that the manifest network domains (`api.app.mrscraper.com`, `api.mrscraper.com`) match the client endpoints and that the runner uses Python 3.12. Check the 660-second plugin request ceiling in `main.py`. Page services default to 300 seconds plus 30 seconds for transport; Scrape brand and Web search use 120 seconds; Status uses 600 seconds. Infrastructure may impose shorter deadlines.

Before packaging, run tests and lint, check dependencies and the lockfile, and review README and PRIVACY against the final code. Packaging and publication are separate release actions; this guide does not perform them.

[Plugin source](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-0.4.0-source/mrscraper)
