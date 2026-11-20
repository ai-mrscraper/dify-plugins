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
            proxy = parameters.get("proxy")
            if isinstance(proxy, str):
                secrets.append(proxy)
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
    def _page_params(
        *,
        url: str,
        timeout: int = 300,
        geo_code: str = "us",
        proxy_country: str = "us",
        super: bool = False,
        wait_until: str = "domcontentloaded",
        proxy: str | None = None,
        max_retries: int | None = None,
        save_result: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "url": url,
            "super": super,
            "waitUntil": wait_until,
            "timeout": timeout,
            "geoCode": geo_code,
            "proxyCountry": proxy_country,
            "saveResult": save_result,
        }
        if proxy is not None:
            params["proxy"] = proxy
        if max_retries is not None:
            params["maxRetries"] = max_retries
        return params

    @classmethod
    def _loading_params(
        cls,
        *,
        block_resources: bool = False,
        wait_for_selector: str | None = None,
        return_cookie: bool = False,
        **page: Any,
    ) -> dict[str, Any]:
        params = cls._page_params(**page)
        if wait_for_selector is not None:
            params["waitForSelector"] = wait_for_selector
        params["blockResources"] = block_resources
        params["returnCookie"] = return_cookie
        return params

    def _page_request(self, params: dict[str, Any]) -> Any:
        return self._request(
            "GET", _endpoint(params), timeout=float(params["timeout"] + TRANSPORT_GRACE_SECONDS)
        )

    def scrape_html(
        self, *, browser_rendering: bool = False, warm_start: bool = False, **page: Any
    ) -> Any:
        """Retrieve the raw HTML of a page. Browser rendering is optional."""
        params = self._loading_params(**page)
        params.update(
            browserRendering=browser_rendering,
            warmStart=warm_start,
            html=True,
            markdown=False,
            screenshot=False,
        )
        return self._page_request(params)

    def scrape_markdown(
        self,
        *,
        browser_rendering: bool = False,
        warm_start: bool = False,
        html: bool = False,
        **page: Any,
    ) -> Any:
        """Retrieve a page as Markdown; including HTML also enables browser rendering."""
        params = self._loading_params(**page)
        params.update(
            # The API fails for html+markdown without browser rendering.
            browserRendering=html or browser_rendering,
            warmStart=warm_start,
            html=html,
            markdown=True,
            screenshot=False,
        )
        return self._page_request(params)

    def get_screenshot(
        self,
        *,
        warm_start: bool = False,
        screenshot: str = "full",
        html: bool = True,
        markdown: bool = False,
        **page: Any,
    ) -> Any:
        """Capture a base64 screenshot of the full page or top viewport."""
        params = self._loading_params(**page)
        params.update(
            browserRendering=True,
            warmStart=warm_start,
            screenshot=screenshot,
            html=html,
            markdown=markdown,
        )
        return self._page_request(params)

    def scrape_json(
        self,
        *,
        prompt: str = DEFAULT_JSON_PROMPT,
        browser_rendering: bool = False,
        html: bool = False,
        screenshot: bool = False,
        **page: Any,
    ) -> Any:
        """Extract structured JSON from a page using a natural-language prompt."""
        params = self._page_params(**page)
        params.update(
            browserRendering=browser_rendering,
            html=html,
            screenshot=screenshot,
            agent="general",
            prompt=prompt,
        )
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

    def web_search(self, *, query: str, country: str = "us", num_results: int = 10) -> Any:
        """Search the web and return ranked results."""
        return self._request(
            "GET",
            _endpoint(
                {
                    "action": "websearch",
                    "query": query,
                    "country": country,
                    "numResults": num_results,
                }
            ),
            timeout=BRAND_AND_SEARCH_TIMEOUT,
        )

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
