# Developing the MrScraper Dify Plugin

The plugin exposes three tools backed by `mrscraper-sdk==0.6.0`: Account, Scraper API, and Web Search. This guide covers the plugin adapter; see the [SDK source](https://github.com/mrscraper-com/sdk-python) for HTTP request construction and the [README](README.md) for user-facing parameters and examples.

## Environment

Use Python 3.12 and run commands from the `mrscraper` directory.

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

Keep runtime dependencies synchronized between `pyproject.toml` and `requirements.txt`, and update `uv.lock` when dependencies change. The Dify SDK and MrScraper SDK versions are pinned for reproducible plugin installation.

## Adapter contract

- `provider/mrscraper.yaml` registers only `mrscraper_account`, `mrscraper_scraper_api`, and `mrscraper_web_search`.
- The provider owns the `api_token` credential and validates it through the SDK's `account()` method. Credentials are never tool parameters.
- Tool YAML files define the Dify interface; the corresponding Python files validate parameters and call the matching SDK method.
- All SDK methods are asynchronous. The Dify adapter runs them through the shared synchronous bridge used by tool invocation and credential validation.
- Pass `browser_rendering` and `stream` to the SDK as `None`, `True`, or `False`, mapping the Dify select values `auto`, `true`, and `false` respectively. Preserve explicit false and zero values for other options.
- Parse `headers` as a JSON object string. Pass `cookie_jar` as a string. The SDK handles request serialization and screenshot/browser-rendering behavior.
- Return the SDK's inner `data` only. Emit objects and arrays as Dify JSON messages, strings unchanged as text, and scalar values as text. HTTP status and response headers are transport metadata and are omitted from tool content.
- Convert SDK authentication, HTTP, network, and parameter errors into useful Dify errors without exposing the provider token.

Web Search's SDK default `raw=True` overrides `format`. Keep this behavior explicit in the schema, descriptions, and tests: parsed JSON requires `raw=False`. Pagination requests one page per call, and explicit region, language, or page options override values parsed from a search URL.

## Verification

Use mocked SDK calls or mocked HTTP transports for automated tests. Tests should establish that the three registered schemas load, inputs reach the correct SDK method, credentials stay at provider level, error messages do not expose the token, and JSON/text outputs retain their native shape. Cover `raw`/`format`, browser-rendering and stream select conversion, explicit false/zero values, and search URL pagination overrides.

Account's safe-summary and the SDK's wire serialization are SDK responsibilities. Adapter tests should focus on Dify behavior and avoid live calls. Run live checks only when explicitly requested and use a token supplied through Dify credentials.

For a Dify development connection, copy `.env.example` to `.env`, configure the deployment's debug connection, then run:

```bash
uv run python -m main
```

Keep `.env` and tokens out of source control and packaged artifacts. For release 0.1.0, review the README migration section because all 18 tool IDs from 0.0.1 were replaced.

## Release consistency

Keep the plugin version consistent across project metadata and `manifest.yaml`. Confirm that the manifest allows only the three hosts documented in the README and uses Python 3.12. Check the 660-second plugin request ceiling in `main.py`. Account defaults to 30 seconds; Scraper API defaults to 120 seconds plus 30 seconds for transport; Web Search defaults to 600 seconds. Infrastructure may impose shorter deadlines.

Before packaging, run tests and lint, check dependencies and the lockfile, and review README and PRIVACY against the final code. Packaging and publication are separate release actions; this guide does not perform them.

[Plugin source](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-three-tools-source/mrscraper)
