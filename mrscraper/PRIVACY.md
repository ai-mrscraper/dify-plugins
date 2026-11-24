# Privacy Policy for the MrScraper Dify Plugin

Last updated: November 23, 2026

This policy describes data processing performed by the MrScraper Dify plugin, version 0.4.0. The plugin calls the MrScraper API at `api.mrscraper.com` (Scrape HTML, Scrape Markdown, Get screenshot, Scrape brand, Scrape JSON, and Web search) and `api.app.mrscraper.com` (Status) over HTTPS. Use of the service is also governed by MrScraper's [Privacy Policy](https://mrscraper.com/privacy-policy) and [Data Protection Policy](https://mrscraper.com/data-protection-policy).

## Data sent to MrScraper

The plugin sends the provider's API token and the information needed for the selected operation:

- **Status:** the authentication token only.
- **Scrape HTML and Scrape Markdown:** the target URL; browser rendering, warm start, and resource blocking settings; selector waiting; geolocation; the cache age; the timeout; the retry limit; and, for Scrape HTML, the requested screenshot.
- **Get screenshot:** the target URL, the screenshot area, selector waiting, geolocation, the cache age, the timeout, and the retry limit. The plugin always renders the page in a browser.
- **Scrape JSON:** the target URL, the extraction prompt (which may include a JSON schema), whether to include the page HTML and a screenshot, and the same loading and page controls as Scrape HTML.
- **Scrape brand:** the target URL.
- **Web search:** the search query, the country, and the requested number of results.

MrScraper fetches the requested content or search results and returns the response to the plugin. Depending on the operation, this may include the raw account status record, page HTML, Markdown, screenshots, extracted JSON with execution metadata, brand data, or search data. Target content and extraction prompts may contain personal or confidential information.

The plugin sends operation data to MrScraper over HTTPS.

Target websites are accessed by the MrScraper service rather than directly by the plugin.

## Credentials and returned data

Dify stores the provider-level API token under the deployment's credential controls and supplies it at runtime. The token is not a tool parameter. The plugin sends it only in the `Authorization: Bearer` and `x-api-token` request headers; it is not included in request URLs. Target URLs, prompts, queries, and options are sent in the HTTPS request query string (Scrape JSON sends the URL, prompt, and agent in a JSON body when the URL would exceed 8,000 characters). The plugin sanitizes its API token from reported errors.

Status returns the raw account status record as supplied by MrScraper, which can include account identity, subscription, and quota details; restrict access to workflows that use it accordingly. The plugin returns the response data to Dify and omits HTTP status codes and response headers. Page content, extraction results, brand data, and search results are returned as supplied by the service. The page tools (Scrape HTML, Scrape Markdown, Get screenshot, and Scrape JSON) always send `saveResult=true`, so MrScraper stores their results in the user's dashboard Result tab. With `max_age` above 0, MrScraper may return a cached result of the same request.

## Storage and logging

The plugin does not request Dify storage permission and does not implement a database or persistent cache. It does not intentionally log API tokens, request payloads, or response bodies. Results are delivered into the user's Dify execution context. Dify, MrScraper, reverse proxies, infrastructure providers, and target websites may independently retain execution history, request logs, or submitted data according to their configuration and policies.

## Data sharing and retention

The plugin sends operation data to MrScraper. MrScraper may use subprocessors as described in its policies. The plugin has no retention or deletion facility because it does not persist operation data. Direct requests about data retained by Dify to the Dify deployment operator; direct requests about data retained by MrScraper to MrScraper.

## User responsibilities

Submit and process only data you are authorized to access. Choose prompts appropriate for the requested operation. Page tool results are always stored in the MrScraper dashboard, so do not use them for content that must not be retained there. Follow applicable website terms and privacy, copyright, and computer-access laws.

## Contact

For plugin information, see the [source repository](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-0.4.0-source/mrscraper). For support or MrScraper privacy questions, contact `support@mrscraper.com` or use the contact details in MrScraper's privacy policy.
