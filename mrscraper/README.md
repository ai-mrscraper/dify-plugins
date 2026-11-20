# MrScraper for Dify

Use MrScraper in Dify Agents, Chatflows, and Workflows through seven tools: **Status**, **Scrape HTML**, **Scrape Markdown**, **Get screenshot**, **Scrape brand**, **Scrape JSON**, and **Web search**. The plugin calls the MrScraper HTTPS API directly with `httpx`. Descriptions, parameter meanings, and defaults follow the [MrScraper API reference](https://docs.mrscraper.com/docs/api/overview) shared by the MrScraper CLI, SDKs, and integrations.

[Plugin source](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-0.3.0-source/mrscraper) · [Development guide](https://github.com/ai-mrscraper/dify-plugins/blob/feat/mrscraper-0.3.0-source/mrscraper/GUIDE.md) · [Privacy](PRIVACY.md)

## Setup

1. Create or copy an API token in the [MrScraper app](https://app.mrscraper.com/api-tokens).
2. Install the plugin in Dify 1.17.0 or later.
3. Open the MrScraper provider credentials and enter the token under **API Token**.
4. Add one of the seven tools to your Agent or Workflow.

The provider validates the credential with the Status tool. Dify supplies this one provider-level credential at runtime; the API token is never a tool parameter. Every request sends it in the `Authorization: Bearer` and `x-api-token` headers.

Your Dify deployment must allow outbound HTTPS connections to `api.mrscraper.com` and `api.app.mrscraper.com`.

## Tools

| Tool | Tool ID | Description |
| --- | --- | --- |
| [Status](#status) | `mrscraper_status` | Return the raw account status API response without summarizing, redacting body fields, or adding calculated fields. |
| [Scrape HTML](#scrape-html) | `mrscraper_scrape_html` | Retrieve the raw HTML of a page. Browser rendering is optional. |
| [Scrape Markdown](#scrape-markdown) | `mrscraper_scrape_markdown` | Retrieve a page as Markdown. Including HTML also enables browser rendering and returns both outputs as JSON. |
| [Get screenshot](#get-screenshot) | `mrscraper_get_screenshot` | Capture a base64 screenshot of the full page or top viewport. Browser rendering is always enabled. |
| [Scrape brand](#scrape-brand) | `mrscraper_scrape_brand` | Extract a website's colors, typography, logos, and social links as JSON. |
| [Scrape JSON](#scrape-json) | `mrscraper_scrape_json` | Extract structured JSON from a page using a natural-language prompt. Append Json Schema: and a JSON schema to shape the output. |
| [Web search](#web-search) | `mrscraper_web_search` | Search the web and return ranked results with titles, URLs, descriptions, and sources. |

## Shared parameters

HTML, Markdown, screenshots, and JSON extraction share `url`, `timeout`, `geo_code`, `proxy_country`, `super`, `wait_until`, `proxy`, `max_retries`, and `save_result`. Page defaults are 300 seconds, US geolocation and proxy country, real-device routing off, and dashboard saving off. Leave `max_retries` empty for no retry limit.

HTML, Markdown, and screenshots also accept `block_resources`, `wait_for_selector`, and `return_cookie`. JSON extraction does not accept these controls. Browser rendering is optional for HTML, Markdown, and JSON; screenshots always enable it. Markdown with HTML also enables browser rendering. `warm_start` is available for HTML, Markdown, and screenshots.

Leave an optional input empty to use its default. Country codes are sent in lowercase.

## Status

Return the raw account status API response without summarizing, redacting body fields, or adding calculated fields.

This tool takes no parameters. Authentication comes from the provider credential. The HTTP deadline is fixed at 600 seconds.

The API body contains `message` and `data`. Account details remain nested in `data`, including `subscriptionItem` and `scraperAllowance`. The plugin returns this body unchanged as a JSON message.

```json
{
  "message": "Example response",
  "data": {
    "id": "ACCOUNT_ID",
    "tokenLimit": 100000,
    "tokenUsage": 2500,
    "stripeStatus": "active",
    "user": {
      "name": "Example user",
      "email": "user@example.com",
      "isVerified": true
    },
    "subscriptionItem": {
      "name": "Example plan",
      "tokenLimit": 100000
    },
    "scraperAllowance": {
      "remaining": 97500,
      "plans": [
        {
          "remaining": 97500
        }
      ]
    }
  }
}
```

## Scrape HTML

Retrieve the raw HTML of a page. Browser rendering is optional.

| Parameter | HTTP field | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `url` | `url` | string | Required | Absolute HTTP or HTTPS URL of the page to process. |
| `timeout` | `timeout` | integer | `300` | Page load timeout in seconds, from 1 to 300. The HTTP request allows 30 additional seconds. |
| `geo_code` | `geoCode` | string | `"us"` | Two-letter country code to load the page from, sent in lowercase. |
| `proxy_country` | `proxyCountry` | string | `"us"` | Two-letter country code of the proxy server, sent in lowercase. |
| `super` | `super` | boolean | `false` | Whether to route the request through real devices. |
| `wait_until` | `waitUntil` | select: `domcontentloaded`, `load`, `networkidle0`, `networkidle2` | `"domcontentloaded"` | Navigation completion event to wait for: domcontentloaded, load, networkidle0, or networkidle2. |
| `proxy` | `proxy` | string | Omitted | Custom proxy URL used to load the page. |
| `max_retries` | `maxRetries` | integer | Omitted | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit. |
| `save_result` | `saveResult` | boolean | `false` | Whether to save the result to the dashboard Result tab. |
| `block_resources` | `blockResources` | boolean | `false` | Whether to block images, fonts, and stylesheets while loading the page. |
| `wait_for_selector` | `waitForSelector` | string | Omitted | Wait for the page to contain the specified CSS selector before returning the result. |
| `return_cookie` | `returnCookie` | boolean | `false` | Whether to include browser session cookies in the response. |
| `browser_rendering` | `browserRendering` | boolean | `false` | Whether to render the page in a browser before returning the result. |
| `warm_start` | `warmStart` | boolean | `false` | Whether to enable warm start for more reliable scraping, at the cost of additional latency. |

Example input:

```json
{
  "url": "https://example.com",
  "browser_rendering": true,
  "warm_start": true,
  "wait_for_selector": "body",
  "timeout": 120
}
```

The default response body is HTML text, returned as a text message. Additional controls can cause the API to return JSON; the returned structure is preserved.

## Scrape Markdown

Retrieve a page as Markdown. Including HTML also enables browser rendering and returns both outputs as JSON.

| Parameter | HTTP field | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `url` | `url` | string | Required | Absolute HTTP or HTTPS URL of the page to process. |
| `timeout` | `timeout` | integer | `300` | Page load timeout in seconds, from 1 to 300. The HTTP request allows 30 additional seconds. |
| `geo_code` | `geoCode` | string | `"us"` | Two-letter country code to load the page from, sent in lowercase. |
| `proxy_country` | `proxyCountry` | string | `"us"` | Two-letter country code of the proxy server, sent in lowercase. |
| `super` | `super` | boolean | `false` | Whether to route the request through real devices. |
| `wait_until` | `waitUntil` | select: `domcontentloaded`, `load`, `networkidle0`, `networkidle2` | `"domcontentloaded"` | Navigation completion event to wait for: domcontentloaded, load, networkidle0, or networkidle2. |
| `proxy` | `proxy` | string | Omitted | Custom proxy URL used to load the page. |
| `max_retries` | `maxRetries` | integer | Omitted | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit. |
| `save_result` | `saveResult` | boolean | `false` | Whether to save the result to the dashboard Result tab. |
| `block_resources` | `blockResources` | boolean | `false` | Whether to block images, fonts, and stylesheets while loading the page. |
| `wait_for_selector` | `waitForSelector` | string | Omitted | Wait for the page to contain the specified CSS selector before returning the result. |
| `return_cookie` | `returnCookie` | boolean | `false` | Whether to include browser session cookies in the response. |
| `browser_rendering` | `browserRendering` | boolean | `false` | Whether to render the page in a browser before returning the result. |
| `warm_start` | `warmStart` | boolean | `false` | Whether to enable warm start for more reliable scraping, at the cost of additional latency. |
| `html` | `html` | boolean | `false` | Whether to include the page HTML in the response. |

Example input:

```json
{
  "url": "https://example.com",
  "html": true,
  "warm_start": true
}
```

The default response body is Markdown text, returned as a text message. Enabling HTML returns JSON containing both HTML and Markdown:

```json
{
  "html": "<html>...</html>",
  "markdown": "# Example page\n\n..."
}
```

## Get screenshot

Capture a base64 screenshot of the full page or top viewport. Browser rendering is always enabled.

| Parameter | HTTP field | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `url` | `url` | string | Required | Absolute HTTP or HTTPS URL of the page to process. |
| `timeout` | `timeout` | integer | `300` | Page load timeout in seconds, from 1 to 300. The HTTP request allows 30 additional seconds. |
| `geo_code` | `geoCode` | string | `"us"` | Two-letter country code to load the page from, sent in lowercase. |
| `proxy_country` | `proxyCountry` | string | `"us"` | Two-letter country code of the proxy server, sent in lowercase. |
| `super` | `super` | boolean | `false` | Whether to route the request through real devices. |
| `wait_until` | `waitUntil` | select: `domcontentloaded`, `load`, `networkidle0`, `networkidle2` | `"domcontentloaded"` | Navigation completion event to wait for: domcontentloaded, load, networkidle0, or networkidle2. |
| `proxy` | `proxy` | string | Omitted | Custom proxy URL used to load the page. |
| `max_retries` | `maxRetries` | integer | Omitted | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit. |
| `save_result` | `saveResult` | boolean | `false` | Whether to save the result to the dashboard Result tab. |
| `block_resources` | `blockResources` | boolean | `false` | Whether to block images, fonts, and stylesheets while loading the page. |
| `wait_for_selector` | `waitForSelector` | string | Omitted | Wait for the page to contain the specified CSS selector before returning the result. |
| `return_cookie` | `returnCookie` | boolean | `false` | Whether to include browser session cookies in the response. |
| `warm_start` | `warmStart` | boolean | `false` | Whether to enable warm start for more reliable scraping, at the cost of additional latency. |
| `screenshot` | `screenshot` | select: `full`, `top` | `"full"` | Screenshot area to capture: full for the entire page or top for the top viewport. |
| `html` | `html` | boolean | `true` | Whether to include the page HTML in the response. |
| `markdown` | `markdown` | boolean | `false` | Whether to include the page Markdown in the response. |

Browser rendering is always enabled. `warm_start` is available for screenshots in this plugin in addition to the standard service reference.

Example input:

```json
{
  "url": "https://example.com",
  "screenshot": "top",
  "html": false,
  "markdown": true,
  "warm_start": true
}
```

The response body is JSON containing a base64 screenshot and the requested page outputs. The API can still include HTML when HTML output is disabled.

```json
{
  "html": "<html>...</html>",
  "screenshot": "BASE64_PNG_DATA",
  "markdown": "# Example page\n\n..."
}
```

## Scrape brand

Extract a website's colors, typography, logos, and social links as JSON.

| Parameter | HTTP field | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `url` | `url` | string | Required | Absolute HTTP or HTTPS URL of the page to process. |

The plugin sends `action=brand-scraping`, `url`, and `bundle=none`. Page controls are not accepted. The HTTP deadline is fixed at 120 seconds.

Example input:

```json
{
  "url": "https://example.com"
}
```

The API body contains `message` and a `data` object with `job_id`, `status`, `url`, `final_url`, `brand`, and `error`.

```json
{
  "data": {
    "job_id": "JOB_ID",
    "status": "succeeded",
    "url": "https://example.com",
    "final_url": "https://example.com",
    "brand": {
      "name": "Example brand",
      "colors": {
        "background": "#ffffff",
        "text": "#222222"
      },
      "typography": {
        "body": {
          "font_family": "Example font"
        }
      }
    },
    "error": null,
    "bundle_url": null
  },
  "message": "Example response"
}
```

## Scrape JSON

Extract structured JSON from a page using a natural-language prompt. Append Json Schema: and a JSON schema to shape the output.

| Parameter | HTTP field | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `url` | `url` | string | Required | Absolute HTTP or HTTPS URL of the page to process. |
| `timeout` | `timeout` | integer | `300` | Page load timeout in seconds, from 1 to 300. The HTTP request allows 30 additional seconds. |
| `geo_code` | `geoCode` | string | `"us"` | Two-letter country code to load the page from, sent in lowercase. |
| `proxy_country` | `proxyCountry` | string | `"us"` | Two-letter country code of the proxy server, sent in lowercase. |
| `super` | `super` | boolean | `false` | Whether to route the request through real devices. |
| `wait_until` | `waitUntil` | select: `domcontentloaded`, `load`, `networkidle0`, `networkidle2` | `"domcontentloaded"` | Navigation completion event to wait for: domcontentloaded, load, networkidle0, or networkidle2. |
| `proxy` | `proxy` | string | Omitted | Custom proxy URL used to load the page. |
| `max_retries` | `maxRetries` | integer | Omitted | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit. |
| `save_result` | `saveResult` | boolean | `false` | Whether to save the result to the dashboard Result tab. |
| `prompt` | `prompt` | string | `"Extract all data as complete as possible."` | Instructions describing the data to extract. Append Json Schema: and a JSON schema to shape the output. |
| `browser_rendering` | `browserRendering` | boolean | `false` | Whether to render the page in a browser before returning the result. |
| `html` | `html` | boolean | `false` | Whether to include the page HTML in the response. |
| `screenshot` | `screenshot` | boolean | `false` | Whether to include a base64 screenshot in the response. |

The plugin sends `agent=general`. When the encoded `GET` URL would exceed 8,000 characters, the plugin sends `POST` instead, moving `url`, `prompt`, and `agent` to a JSON body.

Example input:

```json
{
  "url": "https://example.com",
  "prompt": "Extract the first 2 items with title and price. Json Schema: {\"type\":\"array\",\"items\":{\"type\":\"object\",\"properties\":{\"title\":{\"type\":\"string\"},\"price\":{\"type\":\"string\"}},\"required\":[\"title\",\"price\"]}}",
  "browser_rendering": true
}
```

Extraction results are in the body's `data` field and follow the requested schema. Response metadata includes `thread_id`, `token_usage`, `status`, `error`, `runtime`, and `cookies`. `html`, `markdown`, and `screenshot` can be empty strings when not requested.

```json
{
  "success": true,
  "data": [
    {
      "title": "Example item",
      "price": "10.00"
    }
  ],
  "thread_id": "THREAD_ID",
  "token_usage": 1,
  "html": "",
  "markdown": "",
  "screenshot": "",
  "status": "Results ready",
  "error": "",
  "runtime": 1.23,
  "cookies": []
}
```

## Web search

Search the web and return ranked results with titles, URLs, descriptions, and sources.

| Parameter | HTTP field | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `query` | `query` | string | Required | Search query text, trimmed before sending, containing 1 to 1000 characters. |
| `country` | `country` | string | `"us"` | Two-letter country code to search from, sent in lowercase. |
| `num_results` | `numResults` | integer | `10` | Number of search results to request, as an integer from 10 to 100. Fewer results may be returned. |

The plugin sends `action=websearch`. The HTTP deadline is fixed at 120 seconds.

Example input:

```json
{
  "query": "site:example.com documentation",
  "country": "id",
  "num_results": 20
}
```

The API body contains `success`, `message`, a `data` array, and `tokenUsage`. Each result includes `rank`, `title`, `url`, `description`, and `source`.

```json
{
  "success": true,
  "message": "Example response",
  "data": [
    {
      "rank": 1,
      "title": "Example result",
      "url": "https://example.com",
      "description": "Example result description.",
      "source": "example.com"
    }
  ],
  "tokenUsage": 1
}
```

Response examples show selected keys and types observed in live API responses. Values are placeholders; page content, base64 images, and arrays are abbreviated. Actual responses may contain additional fields.

## Outputs and timeouts

JSON objects and arrays from the API become Dify JSON messages, HTML, Markdown, and other text become unchanged text messages, and binary responses become blob messages. HTTP status codes and response headers are not returned as workflow content.

Page tools (HTML, Markdown, screenshot, and JSON) allow `timeout` plus 30 seconds for the HTTP request, up to 330 seconds. Scrape brand and Web search use 120 seconds; Status uses 600 seconds. The plugin's maximum request timeout is 660 seconds; Dify, reverse proxies, and infrastructure may impose shorter limits. Live page and search calls consume MrScraper account quota.

## Upgrading

### From 0.2.0 to 0.3.0

Version 0.3.0 replaces the Account and Scraper API tools with the seven standard services. Recreate affected Agent and Workflow tool nodes and reconnect their inputs and outputs:

- **Account** (`mrscraper_account`) → **Status** (`mrscraper_status`). Status returns the raw account status body instead of the previous summary, and it has no `timeout` parameter.
- **Scraper API** (`mrscraper_scraper_api`) → **Scrape HTML**, **Scrape Markdown**, or **Get screenshot**, depending on the output you need. `home_page` is now `warm_start`. `screenshot` is now `full` or `top` on Get screenshot.
- The `use_proxy`, `bypass_proxy`, `cookie_jar`, `headers`, `token_cap`, `stream`, and `discard_token_secret` options were removed. The `browser_rendering` select (`auto`/`true`/`false`) is now a boolean that defaults to `false`.
- Page defaults changed to the standard values: `timeout` 300 seconds (previously 120), `geo_code` and `proxy_country` `us`, and no retry limit unless `max_retries` is set (previously 3).
- **Web search** keeps its tool ID and `query`, `country`, and `num_results` inputs. It now sends `GET` with query parameters, `country` defaults to `us`, and the request deadline is 120 seconds.
- New tools: **Scrape brand** and **Scrape JSON**.
- The API token is no longer sent in the request URL; it is sent only in request headers.

### Earlier versions

Version 0.2.0 changed Web Search to `query`, `country`, and `num_results`. Version 0.1.0 replaced all 18 tool IDs from 0.0.1; the former extraction, crawl, reusable scraper creation, scraper rerun, and saved-result operations have no equivalent.

## Privacy and support

Review [PRIVACY.md](PRIVACY.md) for the data sent to MrScraper, including URLs, queries, prompts, and proxy settings. Use content you are authorized to access and process.

For plugin development, see the [source](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-0.3.0-source/mrscraper) and [GUIDE.md](https://github.com/ai-mrscraper/dify-plugins/blob/feat/mrscraper-0.3.0-source/mrscraper/GUIDE.md). Contact `support@mrscraper.com` for support.
