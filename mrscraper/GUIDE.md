# Developing the MrScraper Dify Plugin

The plugin exposes three tools: Account, Scraper API, and Web Search. `common/client.py` calls the MrScraper HTTPS API directly with `httpx`. See the [README](README.md) for user-facing parameters and examples.

## Environment

Use Python 3.12 and run commands from the `mrscraper` directory.

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

Keep runtime dependencies synchronized between `pyproject.toml` and `requirements.txt`, and update `uv.lock` when dependencies change. The `dify-plugin` and `httpx` versions are pinned for reproducible plugin installation.

## API contract

- **Account:** `GET https://api.app.mrscraper.com/api/v1/subscription-accounts` with `Authorization: Bearer <token>` and `x-api-token`. The client returns a safe summary that excludes API keys and billing identifiers.
- **Scraper API:** `GET https://api.mrscraper.com` with the `x-api-token` header. Everything goes in the query string: `token`, `url`, `html`, `markdown`, `screenshot`, `timeout`, `geoCode`, `maxRetries`, `tokenCap`, and the optional page controls (`proxyCountry`, `browserRendering`, `super`, `useProxy=false`, `proxy`, `waitForSelector`, `waitUntil`, `warmStart`, `blockResources`, `bypassProxy`, `cookieJar`, `headers` as a JSON string, `stream`). Do not use `POST`: the service forwards the request method to the target site. A screenshot forces `browserRendering=true`. At least one of `html`, `markdown`, or `screenshot` must be true. HTML only returns `text/html`; any combination with Markdown or a screenshot returns JSON.
- **Web Search:** `POST https://api.mrscraper.com` with `x-api-token` and `Content-Type: application/json`, body `{"action": "websearch", "query": "...", "country": "us", "numResults": 10}`. `numResults` must be an integer from 10 to 100; omit `country` when unset. The response is `{"success", "message", "data": [{"rank", "title", "url", "description", "source"}]}`.
- A `401` response means the token is invalid.

## Adapter contract

- `provider/mrscraper.yaml` registers only `mrscraper_account`, `mrscraper_scraper_api`, and `mrscraper_web_search`.
- The provider owns the `api_token` credential and validates it through the Account request. Credentials are never tool parameters.
- Tool YAML files define the Dify interface; `common/parameters.py` validates parameters before any HTTP request, and the corresponding Python files call the matching client method.
- Map the Dify select values `auto`, `true`, and `false` for `browser_rendering` and `stream` to `None`, `True`, and `False`. Preserve explicit false and zero values for other options.
- Parse `headers` as a JSON object string. Pass `cookie_jar` as a string.
- Emit objects and arrays as Dify JSON messages, strings unchanged as text, binary data as blobs, and scalar values as text. HTTP status and response headers are omitted from tool content.
- Convert HTTP, network, and parameter errors into useful Dify errors without exposing the provider token or configured proxy, cookie, header, and discard-token secrets.

## Verification

Automated tests replace `MrscraperClient.transport` with an in-memory `httpx.MockTransport`. Tests should establish that the three registered schemas load, inputs reach the correct endpoint with the correct method, query, and body, credentials stay at provider level, error messages do not expose secrets, and JSON/text outputs retain their native shape.

Run live checks only when explicitly requested, with a token supplied through the environment or Dify credentials. Never write tokens to files.

For a Dify development connection, copy `.env.example` to `.env`, configure the deployment's debug connection, then run:

```bash
uv run python -m main
```

Keep `.env` and tokens out of source control and packaged artifacts.

## Release consistency

Keep the plugin version consistent across `pyproject.toml` and `manifest.yaml`. Confirm that the manifest network domains (`api.app.mrscraper.com`, `api.mrscraper.com`) match the client endpoints and that the runner uses Python 3.12. Check the 660-second plugin request ceiling in `main.py`. Account defaults to 30 seconds; Scraper API defaults to 120 seconds plus 30 seconds for transport; Web Search uses 600 seconds. Infrastructure may impose shorter deadlines.

Before packaging, run tests and lint, check dependencies and the lockfile, and review README and PRIVACY against the final code. Packaging and publication are separate release actions; this guide does not perform them.

[Plugin source](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-0.2.0-source/mrscraper)
