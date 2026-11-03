# MrScraper for Dify

Use MrScraper in Dify Agents, Chatflows, and Workflows through three tools: **Account**, **Scraper API**, and **Web Search**. The plugin calls the MrScraper HTTPS API directly with `httpx`.

[Plugin source](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-0.2.0-source/mrscraper) · [Development guide](https://github.com/ai-mrscraper/dify-plugins/blob/feat/mrscraper-0.2.0-source/mrscraper/GUIDE.md) · [Privacy](PRIVACY.md)

## Setup

1. Create or copy an API token in the [MrScraper app](https://app.mrscraper.com).
2. Install the plugin in Dify 1.17.0 or later.
3. Open the MrScraper provider credentials and enter the token under **API Token**.
4. Add one of the three tools to your Agent or Workflow.

The provider validates the credential with the Account tool. Dify supplies this one provider-level credential at runtime; the API token is never a tool parameter.

Your Dify deployment must allow outbound HTTPS connections to `api.mrscraper.com` and `api.app.mrscraper.com`.

## Tools

| Tool | Tool ID | Purpose |
| --- | --- | --- |
| Account | `mrscraper_account` | Read account identity, subscription, token quota, and rate limits. |
| Scraper API | `mrscraper_scraper_api` | Fetch a public web page as rendered HTML, Markdown, screenshot, or a combination. |
| Web Search | `mrscraper_web_search` | Search the web for real-time results: website URLs, titles, and descriptions. |

### Account

Call Account with no parameters, or set `timeout` to a positive number of seconds. The default is `30`.

The result contains `subscription_status`, `enterprise`, `token_usage`, `token_limit`, `token_remaining`, `usage_percent`, `rate_limit`, `rate_ttl`, `auto_renew`, `ends_at`, and `user` with `name`, `email`, and `verified`. Remaining tokens are clamped to zero when usage exceeds the limit. API keys and billing identifiers are excluded from this summary.

### Scraper API

Fetch a public web page as rendered HTML, Markdown, screenshot, or a combination. Only `url` is required. To fetch HTML, Markdown, and a screenshot together:

```json
{
  "url": "https://books.toscrape.com/",
  "html": true,
  "markdown": true,
  "screenshot": true
}
```

At least one of `html`, `markdown`, or `screenshot` must be true. `screenshot=true` enables browser rendering, including when `browser_rendering` is set to `"false"`.

| Parameter | Default | Purpose |
| --- | --- | --- |
| `url` | Required | Absolute HTTP or HTTPS page URL. |
| `html`, `markdown`, `screenshot` | `true`, `false`, `false` | Requested outputs. A screenshot also enables browser rendering. |
| `timeout` | `120` | Page timeout in seconds, from 1 to 300. |
| `geo_code`, `proxy_country` | `"US"`, unset | Geolocation and optional proxy country. |
| `browser_rendering` | `"auto"` | Select `"auto"`, `"true"`, or `"false"`; auto lets the API choose its rendering fallback. |
| `super` | `false` | Enable real device routing. |
| `use_proxy`, `proxy` | `true`, unset | Allow proxy use or supply `username:password@host:port`. |
| `home_page` | `false` | Visit the site root before the target page. |
| `wait_for_selector`, `wait_until` | Unset | Wait for a CSS selector or a page lifecycle event such as `domcontentloaded`. |
| `block_resources`, `bypass_proxy` | `false`, `false` | Block images, CSS, and fonts, or enable the API's proxy bypass behavior. |
| `cookie_jar` | Unset | Cookie configuration string, such as `domain=example.com&country=us&max_used=100&max_age=50m`. |
| `headers` | Unset | Target request headers as a JSON object string with string values, such as `{"accept-language":"en-US"}`. |
| `max_retries`, `token_cap` | `3`, unset | Nonnegative retry count and optional nonnegative token budget. |
| `stream` | `"auto"` | Select `"auto"`, `"true"`, or `"false"`; auto omits the option. The plugin buffers the response. |
| `discard_token_secret` | Unset | Optional `x-discard-token-secret` request header. |

The plugin sends a `GET` request to `https://api.mrscraper.com` with the target URL and all options in the query string.

Requesting HTML only returns the page HTML as a text message. Any combination that includes Markdown or a screenshot returns a JSON object such as `{"html": "...", "markdown": "...", "screenshot": "<base64>"}`, containing the requested keys. The screenshot is a base64-encoded image inside that object; the plugin does not create a separate Dify file.

### Web Search

Search the web for real-time results: website URLs, titles, and descriptions.

```json
{
  "query": "e-menessaptieka.lv linkedin",
  "country": "us",
  "num_results": 10
}
```

| Parameter | Default | Purpose |
| --- | --- | --- |
| `query` | Required | The search query. |
| `country` | Unset | Optional country code for localized results, such as `us`. When unset, the service default applies. |
| `num_results` | `10` | Number of results, an integer from 10 to 100. |

The result is a JSON object:

```json
{
  "success": true,
  "message": "Search completed",
  "data": [
    {
      "rank": 1,
      "title": "...",
      "url": "https://...",
      "description": "...",
      "source": "..."
    }
  ]
}
```

## Outputs and timeouts

Objects and arrays from the API become Dify JSON messages, HTML and other strings become unchanged text messages, and binary responses become blob messages. HTTP status codes and response headers are not returned as workflow content. Account returns its safe summary object.

Account defaults to a 30-second request timeout. Scraper API defaults to a 120-second page timeout and allows 30 additional seconds for transport. Web Search uses a 600-second request timeout. The plugin's maximum request timeout is 660 seconds; Dify, reverse proxies, and infrastructure may impose shorter limits. Setting `stream="true"` does not make Dify output stream incrementally.

## Upgrading

### From 0.1.x to 0.2.0

Tool IDs are unchanged, but Web Search has new parameters. Update existing Web Search nodes:

- Pass the search text in `query` (previously `url`).
- Use `country` for localized results and `num_results` (10 to 100) for the number of results.
- `raw`, `format`, `region`, `language`, `page`, `render_js`, and `timeout` were removed. Results are always returned as JSON.

Scraper API keeps its parameters and adds `wait_until`. It now sends every option, including `url`, `max_retries`, and `token_cap`, in a `GET` query string. Account is unchanged.

### From 0.0.1

Version 0.1.0 replaced all 18 tool IDs from 0.0.1 with the three IDs listed above. Recreate affected Agent and Workflow tool nodes and reconnect their inputs and outputs. The former extraction, crawl, reusable scraper creation, scraper rerun, and saved-result operations have no equivalent.

## Privacy and support

Review [PRIVACY.md](PRIVACY.md) for the data sent to MrScraper, including URLs, queries, target headers, cookie configuration, and proxy settings. Use content you are authorized to access and process.

For plugin development, see the [source](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-0.2.0-source/mrscraper) and [GUIDE.md](https://github.com/ai-mrscraper/dify-plugins/blob/feat/mrscraper-0.2.0-source/mrscraper/GUIDE.md). Contact `support@mrscraper.com` for support.
