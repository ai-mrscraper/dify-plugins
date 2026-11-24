from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, quote_plus, urlencode

import httpx

API_URL = "https://api.mrscraper.com"
ACCOUNT_URL = "https://api.app.mrscraper.com/api/v1/subscription-accounts"
DEFAULT_JSON_PROMPT = "Extract all data as complete as possible."
STATUS_TIMEOUT = 600.0
BRAND_AND_SEARCH_TIMEOUT = 120.0
TRANSPORT_GRACE_SECONDS = 30
MAX_GET_URL_LENGTH = 8000
TEXT_TYPES = {"application/xml", "application/xhtml+xml", "application/javascript"}
OPERATIONS = frozenset(
    {
        "status",
        "scrape_html",
        "scrape_markdown",
        "get_screenshot",
        "scrape_brand",
        "scrape_json",
        "web_search",
    }
)
UNAUTHORIZED_MESSAGE = (
    "Unauthorized or invalid token. Please go to https://app.mrscraper.com to get your token."
)


class MrscraperAPIError(RuntimeError):
    """A safe, user-facing MrScraper API error."""


def sanitize_error(message: str, secrets: list[str]) -> str:
    values = {
        encoded
        for secret in secrets
        if secret
        for variant in (
            secret,
            json.dumps(secret)[1:-1],
            json.dumps(secret, ensure_ascii=False)[1:-1],
        )
        for encoded in (variant, quote(variant, safe=""), quote_plus(variant))
    }
    for value in sorted(values, key=len, reverse=True):
        message = message.replace(value, "[REDACTED]")
    return message


def _endpoint(params: dict[str, Any]) -> str:
    """Serialize query values the way the MrScraper SDKs do: booleans become true/false."""
    values = {
        key: str(value).lower() if isinstance(value, bool) else str(value)
        for key, value in params.items()
    }
    return f"{API_URL}?{urlencode(values)}"


class MrscraperClient:
    """Synchronous HTTP client for the seven MrScraper services.

    Methods expect parameters already validated by ``common.parameters``.
    """

    # Tests replace this with an in-memory transport.
    transport: httpx.BaseTransport | None = None

    def __init__(self, token: str) -> None:
        if not isinstance(token, str) or not token.strip():
            raise MrscraperAPIError("MrScraper API token is required.")
        self._token = token.strip()

    def invoke(self, operation: str, parameters: dict[str, Any]) -> Any:
        if operation not in OPERATIONS:
            raise ValueError("Unsupported MrScraper operation.")
        try:
            return getattr(self, operation)(**parameters)
        except (MrscraperAPIError, httpx.HTTPError, ValueError) as exc:
            secrets = [self._token]
            message = str(exc)
            if isinstance(exc, httpx.HTTPError):
                message = f"MrScraper request failed: {type(exc).__name__}: {exc}"
            raise MrscraperAPIError(sanitize_error(message, secrets)) from None

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "x-api-token": self._token,
        }

    # Status

    def status(self) -> Any:
        """Return the raw account status API response body."""
        return self._request("GET", ACCOUNT_URL, timeout=STATUS_TIMEOUT)

    # Page services

    @staticmethod
    def _page_fields(
        *,
        url: str,
        timeout: int = 300,
        wait_for_selector: str | None = None,
        geo_code: str | None = None,
        max_age: int = 0,
        max_retries: int | None = None,
        browser_rendering: bool | None = None,
        warm_start: bool | None = None,
        block_resources: bool | None = None,
    ) -> dict[str, Any]:
        """Return the shared fields in the documented request order, without unset values."""
        fields = {
            "browserRendering": browser_rendering,
            "timeout": timeout,
            "warmStart": warm_start,
            "blockResources": block_resources,
            "waitForSelector": wait_for_selector,
            "geoCode": geo_code,
            # Results are always saved to the dashboard; saveResult is not an input.
            "saveResult": True,
            "maxAge": max_age,
            "maxRetries": max_retries,
        }
        return {"url": url} | {key: value for key, value in fields.items() if value is not None}

    def _page_request(self, params: dict[str, Any]) -> Any:
        return self._request(
            "GET", _endpoint(params), timeout=float(params["timeout"] + TRANSPORT_GRACE_SECONDS)
        )

    @staticmethod
    def _after_url(fixed: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
        """Place a service's fixed fields right after url."""
        return {"url": fields["url"], **fixed} | {k: v for k, v in fields.items() if k != "url"}

    def scrape_html(
        self,
        *,
        warm_start: bool = False,
        block_resources: bool = False,
        screenshot: str | bool = False,
        **page: Any,
    ) -> Any:
        """Retrieve the raw HTML of a page. Browser rendering is optional."""
        fields = self._page_fields(warm_start=warm_start, block_resources=block_resources, **page)
        return self._page_request(
            self._after_url({"html": True, "markdown": False}, fields) | {"screenshot": screenshot}
        )

    def scrape_markdown(
        self, *, warm_start: bool = False, block_resources: bool = False, **page: Any
    ) -> Any:
        """Retrieve a page as clean Markdown. Browser rendering is optional."""
        fields = self._page_fields(warm_start=warm_start, block_resources=block_resources, **page)
        return self._page_request(
            self._after_url({"markdown": True, "html": False, "screenshot": False}, fields)
        )

    def get_screenshot(self, *, screenshot: str = "full", **page: Any) -> Any:
        """Capture a base64 PNG screenshot of the full page, the first viewport, or a viewport."""
        fields = self._page_fields(browser_rendering=True, **page)
        return self._page_request(
            self._after_url({"screenshot": screenshot, "html": False, "markdown": False}, fields)
        )

    def scrape_json(
        self,
        *,
        prompt: str = DEFAULT_JSON_PROMPT,
        html: bool = True,
        screenshot: bool = False,
        warm_start: bool = False,
        block_resources: bool = False,
        **page: Any,
    ) -> Any:
        """Extract structured JSON from a page using a natural-language prompt."""
        fields = self._page_fields(warm_start=warm_start, block_resources=block_resources, **page)
        params = self._after_url({"prompt": prompt, "agent": "general", "html": html}, fields) | {
            "screenshot": screenshot
        }
        timeout = float(params["timeout"] + TRANSPORT_GRACE_SECONDS)
        endpoint = _endpoint(params)
        if len(endpoint) <= MAX_GET_URL_LENGTH:
            return self._request("GET", endpoint, timeout=timeout)
        body = {key: params.pop(key) for key in ("url", "prompt", "agent")}
        return self._request("POST", _endpoint(params), timeout=timeout, payload=body)

    def scrape_brand(self, *, url: str) -> Any:
        """Extract a website's colors, typography, logos, and social links as JSON."""
        return self._request(
            "GET",
            _endpoint({"action": "brand-scraping", "url": url, "bundle": "none"}),
            timeout=BRAND_AND_SEARCH_TIMEOUT,
        )

    def web_search(self, *, query: str, country: str | None = None, num_results: int = 10) -> Any:
        """Search the web and return ranked results."""
        params: dict[str, Any] = {"action": "websearch", "query": query}
        if country is not None:
            params["country"] = country
        params["numResults"] = num_results
        return self._request("GET", _endpoint(params), timeout=BRAND_AND_SEARCH_TIMEOUT)

    def _request(
        self,
        method: str,
        url: str,
        *,
        timeout: float,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        with httpx.Client(transport=self.transport, timeout=timeout) as client:
            response = client.request(
                method,
                url,
                headers=self._headers(),
                content=None if payload is None else json.dumps(payload),
            )
        if response.status_code == 401:
            raise MrscraperAPIError(UNAUTHORIZED_MESSAGE)
        if response.is_error:
            detail = response.text.strip()[:500]
            message = f"MrScraper API returned HTTP {response.status_code}."
            raise MrscraperAPIError(f"{message} {detail}" if detail else message)
        return self._parse(response)

    @staticmethod
    def _parse(response: httpx.Response) -> Any:
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type == "application/json" or content_type.endswith("+json"):
            return response.json()
        if not content_type or content_type.startswith("text/") or content_type in TEXT_TYPES:
            return response.text
        return response.content
