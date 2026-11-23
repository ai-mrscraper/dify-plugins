# MrScraper for Dify

Use MrScraper in Dify Agents, Chatflows, and Workflows through seven tools: **Status**, **Scrape HTML**, **Scrape Markdown**, **Get screenshot**, **Scrape brand**, **Scrape JSON**, and **Web search**. The plugin calls the MrScraper HTTPS API directly with `httpx`. Descriptions, parameter meanings, and defaults follow the [MrScraper API reference](https://docs.mrscraper.com/docs/api/overview) shared by the MrScraper CLI, SDKs, and integrations.

[Plugin source](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-0.4.0-source/mrscraper) · [Development guide](https://github.com/ai-mrscraper/dify-plugins/blob/feat/mrscraper-0.4.0-source/mrscraper/GUIDE.md) · [Privacy](PRIVACY.md)

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
| [Scrape Markdown](#scrape-markdown) | `mrscraper_scrape_markdown` | Retrieve a page as clean Markdown. Browser rendering is optional. |
| [Get screenshot](#get-screenshot) | `mrscraper_get_screenshot` | Capture a base64 PNG screenshot of the full page. Browser rendering is always enabled. |
| [Scrape brand](#scrape-brand) | `mrscraper_scrape_brand` | Extract a website's colors, typography, logos, and social links as JSON. |
| [Scrape JSON](#scrape-json) | `mrscraper_scrape_json` | Extract structured JSON from a page using a natural-language prompt. Append Json Schema: and a JSON schema to shape the output. |
| [Web search](#web-search) | `mrscraper_web_search` | Search the web and return ranked results with titles, URLs, descriptions, and sources. |

## Shared parameters

HTML, Markdown, screenshots, and JSON extraction share `url`, `timeout`, `wait_for_selector`, `geo_code`, `save_result`, `max_age`, `token_cap`, and `max_retries`. Defaults are a 300-second timeout (up to 330), dashboard saving on, and a `max_age` of 0 milliseconds, which always scrapes fresh; `max_age` accepts up to 604800000 (7 days). Leave `geo_code`, `token_cap`, and `max_retries` empty to omit them, so the API loads the page from the United States with no token or retry limit.

HTML, Markdown, and JSON extraction also accept `browser_rendering`, `warm_start`, and `block_resources`; HTML and Markdown also accept `action`. `browser_rendering` is a select: `auto` (the default) leaves it out so the API loads the page without a browser first and switches to one if the request is blocked, `true` always renders, and `false` never does. `wait_for_selector` needs a rendered page, so do not combine it with `false`. Screenshots always render in a browser.

Each tool adds its documented fixed request fields automatically: `html=true` for Scrape HTML, `markdown=true` for Scrape Markdown, `screenshot=full` and `browserRendering=true` for Get screenshot, `action=brand-scraping` and `bundle=none` for Scrape brand, `agent=general` for Scrape JSON, and `action=websearch` for Web search.

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
| `browser_rendering` | `browserRendering` | select: `auto`, `true`, `false` | `auto` (omitted) | Whether to load the page in a browser: true always does and false never does. Omit it to load the page without a browser first and switch to a browser automatically if the request is blocked. |
| `timeout` | `timeout` | integer | `300` | Maximum seconds to wait for the scrape, from 1 to 330. The HTTP request allows 30 additional seconds. |
| `warm_start` | `warmStart` | boolean | `false` | Whether to open the site's home page first to warm the session before loading the target URL. |
| `block_resources` | `blockResources` | boolean | `false` | Whether to block images, fonts, and stylesheets while loading the page. |
| `wait_for_selector` | `waitForSelector` | string | Omitted | CSS selector or text to wait for on the page before returning the result, up to 500 characters. |
| `action` | `action` | string | Omitted | Scraper action that routes the request or simply flags it, useful for separating analytics per domain. |
| `geo_code` | `geoCode` | string | Omitted | Two-letter country code to load the page from, sent in lowercase. |
| `save_result` | `saveResult` | boolean | `true` | Whether to save the result to the dashboard Result tab. |
| `max_age` | `maxAge` | integer | `0` | Return a cached result of the same request when it is newer than the selected age. A cached result costs the same tokens as the original scrape. |
| `token_cap` | `tokenCap` | integer | Omitted | Maximum total tokens the scrape and its retries can use, as a positive integer. Omit this parameter for no limit. |
| `max_retries` | `maxRetries` | integer | Omitted | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit. |
| `screenshot` | `screenshot` | string | `false` | Screenshot to capture with the HTML: false for none, full for the entire page, top for the first viewport, or a WIDTHxHEIGHT viewport from 100 to 3840 pixels with an optional -ZOOM percent from 25 to 300, such as 1280x800 or 1920x1080-75. Any screenshot forces browser rendering. |

The plugin sends `html=true`. Any screenshot forces browser rendering and returns JSON with `html` and `screenshot`.

Example input:

```json
{
  "url": "https://example.com",
  "browser_rendering": "true",
  "warm_start": true,
  "wait_for_selector": "body",
  "timeout": 120
}
```

The response body is HTML text, returned as a text message. With a screenshot, the API returns JSON containing `html` and a base64 `screenshot`:

```json
{
  "html": "<html>...</html>",
  "screenshot": "BASE64_IMAGE_DATA"
}
```

## Scrape Markdown

Retrieve a page as clean Markdown. Browser rendering is optional.

| Parameter | HTTP field | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `url` | `url` | string | Required | Absolute HTTP or HTTPS URL of the page to process. |
| `browser_rendering` | `browserRendering` | select: `auto`, `true`, `false` | `auto` (omitted) | Whether to load the page in a browser: true always does and false never does. Omit it to load the page without a browser first and switch to a browser automatically if the request is blocked. |
| `timeout` | `timeout` | integer | `300` | Maximum seconds to wait for the scrape, from 1 to 330. The HTTP request allows 30 additional seconds. |
| `warm_start` | `warmStart` | boolean | `false` | Whether to open the site's home page first to warm the session before loading the target URL. |
| `block_resources` | `blockResources` | boolean | `false` | Whether to block images, fonts, and stylesheets while loading the page. |
| `wait_for_selector` | `waitForSelector` | string | Omitted | CSS selector or text to wait for on the page before returning the result, up to 500 characters. |
| `action` | `action` | string | Omitted | Scraper action that routes the request or simply flags it, useful for separating analytics per domain. |
| `geo_code` | `geoCode` | string | Omitted | Two-letter country code to load the page from, sent in lowercase. |
| `save_result` | `saveResult` | boolean | `true` | Whether to save the result to the dashboard Result tab. |
| `max_age` | `maxAge` | integer | `0` | Return a cached result of the same request when it is newer than the selected age. A cached result costs the same tokens as the original scrape. |
| `token_cap` | `tokenCap` | integer | Omitted | Maximum total tokens the scrape and its retries can use, as a positive integer. Omit this parameter for no limit. |
| `max_retries` | `maxRetries` | integer | Omitted | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit. |

The plugin sends `markdown=true`.

Example input:

```json
{
  "url": "https://example.com",
  "warm_start": true,
  "max_age": 86400000
}
```

The response body is Markdown text, returned as a text message.

## Get screenshot

Capture a base64 PNG screenshot of the full page. Browser rendering is always enabled.

| Parameter | HTTP field | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `url` | `url` | string | Required | Absolute HTTP or HTTPS URL of the page to process. |
| `timeout` | `timeout` | integer | `300` | Maximum seconds to wait for the scrape, from 1 to 330. The HTTP request allows 30 additional seconds. |
| `wait_for_selector` | `waitForSelector` | string | Omitted | CSS selector or text to wait for on the page before returning the result, up to 500 characters. |
| `geo_code` | `geoCode` | string | Omitted | Two-letter country code to load the page from, sent in lowercase. |
| `save_result` | `saveResult` | boolean | `true` | Whether to save the result to the dashboard Result tab. |
| `max_age` | `maxAge` | integer | `0` | Return a cached result of the same request when it is newer than the selected age. A cached result costs the same tokens as the original scrape. |
| `token_cap` | `tokenCap` | integer | Omitted | Maximum total tokens the scrape and its retries can use, as a positive integer. Omit this parameter for no limit. |
| `max_retries` | `maxRetries` | integer | Omitted | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit. |

The plugin sends `screenshot=full` and `browserRendering=true`; the screenshot area and browser rendering are not inputs.

Example input:

```json
{
  "url": "https://example.com",
  "wait_for_selector": "body",
  "timeout": 120
}
```

The response body is JSON containing a base64 PNG screenshot of the full page and the page HTML.

```json
{
  "html": "<html>...</html>",
  "screenshot": "BASE64_PNG_DATA"
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
| `prompt` | `prompt` | string | `"Extract all data as complete as possible."` | Instructions describing the data to extract. Append Json Schema: and a JSON schema to shape the output. |
| `html` | `html` | boolean | `true` | Whether to include the page HTML in the response. |
| `browser_rendering` | `browserRendering` | select: `auto`, `true`, `false` | `auto` (omitted) | Whether to load the page in a browser: true always does and false never does. Omit it to load the page without a browser first and switch to a browser automatically if the request is blocked. |
| `timeout` | `timeout` | integer | `300` | Maximum seconds to wait for the scrape, from 1 to 330. The HTTP request allows 30 additional seconds. |
| `warm_start` | `warmStart` | boolean | `false` | Whether to open the site's home page first to warm the session before loading the target URL. |
| `block_resources` | `blockResources` | boolean | `false` | Whether to block images, fonts, and stylesheets while loading the page. |
| `wait_for_selector` | `waitForSelector` | string | Omitted | CSS selector or text to wait for on the page before returning the result, up to 500 characters. |
| `geo_code` | `geoCode` | string | Omitted | Two-letter country code to load the page from, sent in lowercase. |
| `save_result` | `saveResult` | boolean | `true` | Whether to save the result to the dashboard Result tab. |
| `max_age` | `maxAge` | integer | `0` | Return a cached result of the same request when it is newer than the selected age. A cached result costs the same tokens as the original scrape. |
| `token_cap` | `tokenCap` | integer | Omitted | Maximum total tokens the scrape and its retries can use, as a positive integer. Omit this parameter for no limit. |
| `max_retries` | `maxRetries` | integer | Omitted | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit. |
| `screenshot` | `screenshot` | boolean | `false` | Whether to include a base64 screenshot in the response. |

The plugin sends `agent=general`. When the encoded `GET` URL would exceed 8,000 characters, the plugin sends `POST` instead, moving `url`, `prompt`, and `agent` to a JSON body.

Example input:

```json
{
  "url": "https://example.com",
  "prompt": "Extract the first 2 items with title and price. Json Schema: {\"type\":\"array\",\"items\":{\"type\":\"object\",\"properties\":{\"title\":{\"type\":\"string\"},\"price\":{\"type\":\"string\"}},\"required\":[\"title\",\"price\"]}}",
  "browser_rendering": "true"
}
```

Extraction results are in the body's `data` field and follow the requested schema. Response metadata includes `thread_id`, `token_usage`, `status`, `error`, `runtime`, and `cookies`. `html` contains the page HTML unless disabled; `markdown` and `screenshot` can be empty strings.

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
  "html": "<html>...</html>",
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
| `country` | `country` | string | Omitted | Two-letter country code to search from, sent in lowercase. |
| `num_results` | `numResults` | integer | `10` | Number of search results to request, as an integer from 10 to 100. Fewer results may be returned. |

The plugin sends `action=websearch`. `country` is omitted unless set, so the API searches from the United States. The HTTP deadline is fixed at 120 seconds.

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

### From 0.3.0 to 0.4.0

Version 0.4.0 matches the Scraper API reference. Tool IDs are unchanged; review the inputs of existing Agent and Workflow tool nodes:

- Removed inputs: `super`, `wait_until`, `proxy_country`, `proxy`, and `return_cookie` on the page tools, `html` on Scrape Markdown, and `screenshot`, `html`, `markdown`, and `warm_start` on Get screenshot. Get screenshot always captures the full page.
- New inputs: `max_age` and `token_cap` on the page tools, `action` on Scrape HTML and Scrape Markdown, and `screenshot` on Scrape HTML (`false`, `full`, `top`, or a custom viewport). Scrape JSON now accepts `warm_start`, `block_resources`, and `wait_for_selector`.
- `browser_rendering` is a select: `auto` (the default) leaves rendering to the API, `true` always renders, and `false` never does.
- Changed defaults: `save_result` is `true`, Scrape JSON's `html` is `true`, `timeout` accepts up to 330 seconds, and `geo_code` and Web search's `country` are omitted unless set, so the API uses the United States.

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

For plugin development, see the [source](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-0.4.0-source/mrscraper) and [GUIDE.md](https://github.com/ai-mrscraper/dify-plugins/blob/feat/mrscraper-0.4.0-source/mrscraper/GUIDE.md). Contact `support@mrscraper.com` for support.
