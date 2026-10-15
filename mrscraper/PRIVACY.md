# Privacy Policy for the MrScraper Dify Plugin

Last updated: October 15, 2026

This policy describes data processing performed by the MrScraper Dify plugin, version 0.1.0. The plugin uses the MrScraper Python SDK (`mrscraper-sdk==0.6.0`) for Account, Scraper API, and Web Search. Use of the service is also governed by MrScraper's [Privacy Policy](https://mrscraper.com/privacy-policy) and [Data Protection Policy](https://mrscraper.com/data-protection-policy).

## Data sent to MrScraper

The plugin sends the provider's API token and the information needed for the selected operation:

- **Account:** the authentication token.
- **Scraper API:** the target URL; requested HTML, Markdown, or screenshot output; rendering and real device routing settings; geolocation and proxy country; a custom proxy value, which may contain proxy credentials; target request headers; cookie-jar configuration; selector waiting and home-page navigation settings; resource and proxy controls; timeout, retries, token budget, and stream options; and an optional discard-token secret.
- **Web Search:** search query text or query fields extracted from a supplied Google search URL, region, language, result page, output format, and JavaScript rendering preference.

MrScraper fetches the requested content or search results and returns the response to the plugin. Depending on the operation, this may include account identity and quota information, page HTML, Markdown, screenshots, or search data. Target content and user-provided headers, cookie configuration, or proxy settings may contain personal or confidential information.

The plugin connects to exactly these MrScraper API hosts over HTTPS:

- `api.app.mrscraper.com` for Account and credential validation;
- `api.mrscraper.com` for Scraper API;
- `sync.scraper.mrscraper.com` for Web Search.

Target websites are accessed by the MrScraper service rather than directly by the plugin.

## Credentials and returned data

Dify stores the provider-level API token under the deployment's credential controls and supplies it at runtime. The token is not a tool parameter. The SDK sends it in authentication headers; Scraper API also includes it in the HTTPS request query. The plugin sanitizes its API token from reported errors.

Account output contains a safe summary of identity, subscription, quota, and rate limits. The SDK excludes API keys and billing identifiers from that summary. The plugin returns the SDK's inner response data to Dify and omits the HTTP envelope and response headers. Page content and search results are returned as supplied by the service.

## Storage and logging

The plugin does not request Dify storage permission and does not implement a database or persistent cache. It does not intentionally log API tokens, request payloads, or response bodies. Results are delivered into the user's Dify execution context. Dify, MrScraper, reverse proxies, infrastructure providers, and target websites may independently retain execution history, request logs, or submitted data according to their configuration and policies.

## Data sharing and retention

The plugin sends operation data to MrScraper. MrScraper may use subprocessors as described in its policies. The plugin has no retention or deletion facility because it does not persist operation data. Direct requests about data retained by Dify to the Dify deployment operator; direct requests about data retained by MrScraper to MrScraper.

## User responsibilities

Submit and process only data you are authorized to access. Choose target headers, cookie configuration, and proxy credentials appropriate for the requested operation. Follow applicable website terms and privacy, copyright, and computer-access laws.

## Contact

For plugin information, see the [source repository](https://github.com/ai-mrscraper/dify-plugins/tree/feat/mrscraper-three-tools-source/mrscraper). For support or MrScraper privacy questions, contact `support@mrscraper.com` or use the contact details in MrScraper's privacy policy.
