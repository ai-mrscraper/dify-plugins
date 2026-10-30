# MrScraper for Dify

Use MrScraper in Dify Agents, Chatflows, and Workflows through three tools: **Account**, **Scraper API**, and **Web Search**. The plugin uses the [MrScraper Python SDK](https://github.com/mrscraper-com/sdk-python), pinned to `mrscraper-sdk==0.6.0`.

[Plugin source](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-three-tools-source/mrscraper) · [Development guide](https://github.com/ai-mrscraper/dify-plugins/blob/feat/mrscraper-three-tools-source/mrscraper/GUIDE.md) · [Privacy](PRIVACY.md)

## Setup

1. Create or copy an API token in the [MrScraper app](https://app.mrscraper.com).
2. Install the plugin in Dify 1.17.0 or later.
3. Open the MrScraper provider credentials and enter the token under **API Token**.
4. Add one of the three tools to your Agent or Workflow.

The provider validates the credential with the Account tool. Dify supplies this one provider-level credential at runtime; the API token is never a tool parameter.

Your Dify deployment must allow outbound HTTPS connections to MrScraper.

## Tools

| Tool | Tool ID | Purpose |
| --- | --- | --- |
| Account | `mrscraper_account` | Read account identity, subscription, token quota, and rate limits. |
| Scraper API | `mrscraper_scraper_api` | Fetch a page as HTML, Markdown, a screenshot, or a combination. |
| Web Search | `mrscraper_web_search` | Search the web to retrieve real-time search results, including relevant website URLs, titles, descriptions, and related questions based on a given query. |

### Account

Call Account with no parameters, or set `timeout` to a positive number of seconds. The default is `30`.

The result contains `subscription_status`, `enterprise`, `token_usage`, `token_limit`, `token_remaining`, `usage_percent`, `rate_limit`, `rate_ttl`, `auto_renew`, `ends_at`, and `user` with `name`, `email`, and `verified`. Remaining tokens are clamped to zero when usage exceeds the limit. The SDK excludes API keys and billing identifiers from this summary.

### Scraper API

Only `url` is required. To fetch HTML, Markdown, and a screenshot together:

```json
{
  "url": "https://example.com",
  "html": true,
  "markdown": true,
  "screenshot": true
}
```

`screenshot=true` enables browser rendering, including when `browser_rendering` is set to `"false"`.

| Parameter | Default | Purpose |
| --- | --- | --- |
| `url` | Required | Absolute HTTP or HTTPS page URL. |
| `html`, `markdown` | `true`, `false` | Request either or both representations. |
| `timeout` | `120` | Page timeout in seconds, from 1 to 300. |
| `geo_code`, `proxy_country` | `"US"`, unset | Geolocation and optional proxy country. |
| `browser_rendering` | `"auto"` | Select `"auto"`, `"true"`, or `"false"`; auto lets the API choose its rendering fallback. |
| `screenshot` | `false` | Request a screenshot and enable browser rendering. |
| `super` | `false` | Enable real device routing. |
| `use_proxy`, `proxy` | `true`, unset | Allow proxy use or supply `username:password@host:port`. |
| `home_page` | `false` | Visit the site root before the target page. |
| `wait_for_selector` | Unset | Wait for a CSS selector. |
| `block_resources`, `bypass_proxy` | `false`, `false` | Block images, CSS, and fonts, or enable the API's proxy bypass behavior. |
| `cookie_jar` | Unset | Cookie configuration string, such as `domain=example.com&country=us&max_used=100&max_age=50m`. |
| `headers` | Unset | Target request headers as a JSON object string with string values, such as `{"accept-language":"en-US"}`. |
| `max_retries`, `token_cap` | `3`, unset | Nonnegative retry count and optional nonnegative token budget. |
| `stream` | `"auto"` | Select `"auto"`, `"true"`, or `"false"`; auto omits the option. The SDK buffers the response. |
| `discard_token_secret` | Unset | Optional `x-discard-token-secret` request header. |

The API may return a string or a structured response containing several representations. Inspect the returned data before assuming it is an HTML string. A screenshot is returned as part of the API response; the plugin does not create a separate Dify file.

### Web Search

Search the web to retrieve real-time search results, including relevant website URLs, titles, descriptions, and related questions based on a given query. Pass the search query in `url`. To request parsed JSON:

```json
{
  "url": "site:example.com products",
  "raw": false,
  "format": "json",
  "region": "us",
  "language": "en",
  "page": 1
}
```

**`raw=true` is the default and requests HTML regardless of `format`.** Set `raw=false` to use `format="json"` or `format="html"`.

| Parameter | Default | Purpose |
| --- | --- | --- |
| `url` | Required | The search query. |
| `raw` | `true` | Request HTML and override `format` when true. |
| `format` | `"json"` | `"json"` or `"html"`, used when `raw=false`. |
| `region`, `language` | Unset | Optional country and language codes for search results. |
| `page` | Unset | Results page number, starting at `1`. |
| `render_js` | `false` | Render JavaScript-dependent result features. |
| `timeout` | `600` | Positive request timeout in seconds. |

Each call retrieves one results page. Set `region` and `language` to customize the search, and use successive calls with different `page` values to paginate.

## Outputs and timeouts

The plugin returns the SDK's inner `data`: objects and arrays become Dify JSON messages, HTML and other strings become unchanged text messages, and scalar values become text. The SDK's HTTP envelope, status code, and response headers are not returned as workflow content. Account returns its safe summary object.

Account defaults to a 30-second request timeout. Scraper API defaults to a 120-second page timeout and allows 30 additional seconds for transport. Web Search defaults to a 600-second request timeout. The plugin's maximum request timeout is 660 seconds; Dify, reverse proxies, and infrastructure may impose shorter limits. Setting `stream="true"` does not make Dify output stream incrementally.

## Upgrading from 0.0.1

Version **0.1.0 is a breaking update**. It removes all 18 previous tool IDs and registers the three IDs listed above. Recreate affected Agent and Workflow tool nodes and reconnect their inputs and outputs.

Use Account for the previous Get Account Info operation, Scraper API for page fetching, and Web Search for search results. Review parameters when recreating nodes: for example, Scraper API uses `super`, `cookie_jar`, and boolean `screenshot`; Web Search accepts query text through `url` and defaults to raw HTML. The former extraction, crawl, reusable scraper creation, scraper rerun, and saved-result operations have no equivalent in this release.

## Privacy and support

Review [PRIVACY.md](PRIVACY.md) for the data sent to MrScraper, including URLs, queries, target headers, cookie configuration, and proxy settings. Use content you are authorized to access and process.

For plugin development, see the [source](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-three-tools-source/mrscraper) and [GUIDE.md](https://github.com/ai-mrscraper/dify-plugins/blob/feat/mrscraper-three-tools-source/mrscraper/GUIDE.md). Contact `support@mrscraper.com` for support.
