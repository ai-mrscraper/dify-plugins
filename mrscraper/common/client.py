from __future__ import annotations

import json
import math
from typing import Any
from urllib.parse import quote, quote_plus, urlencode

import httpx

API_URL = "https://api.mrscraper.com"
ACCOUNT_URL = "https://api.app.mrscraper.com/api/v1/subscription-accounts"
WEB_SEARCH_TIMEOUT = 600.0
TEXT_TYPES = {"application/xml", "application/xhtml+xml", "application/javascript"}
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


def _compact(values: dict[str, Any]) -> dict[str, Any]:
    """Remove unset values while preserving False, 0, and empty strings."""
    return {key: value for key, value in values.items() if value is not None}


def _number_or_zero(value: Any) -> float:
    try:
        parsed = float(value)
    except (ValueError, TypeError):
        return 0
    return parsed if math.isfinite(parsed) else 0


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


class MrscraperClient:
    """Synchronous HTTP client for the MrScraper endpoints used by the plugin."""

    # Tests replace this with an in-memory transport.
    transport: httpx.BaseTransport | None = None

    def __init__(self, token: str) -> None:
        if not isinstance(token, str) or not token.strip():
            raise MrscraperAPIError("MrScraper API token is required.")
        self._token = token.strip()

    def invoke(self, operation: str, parameters: dict[str, Any]) -> Any:
        if operation not in {"account", "scraper_api", "web_search"}:
            raise ValueError("Unsupported MrScraper operation.")
        try:
            return getattr(self, operation)(**parameters)
        except (MrscraperAPIError, httpx.HTTPError, ValueError) as exc:
            secrets = [self._token]
            secrets.extend(
                value
                for name, value in parameters.items()
                if name in {"proxy", "cookie_jar", "discard_token_secret"}
                and isinstance(value, str)
            )
            headers = parameters.get("headers")
            if isinstance(headers, dict):
                secrets.extend(value for value in headers.values() if isinstance(value, str))
            message = str(exc)
            if isinstance(exc, httpx.HTTPError):
                message = f"MrScraper request failed: {type(exc).__name__}: {exc}"
            raise MrscraperAPIError(sanitize_error(message, secrets)) from None

    def account(self, *, timeout: float = 30.0) -> dict[str, Any]:
        """Return a safe summary of identity, subscription, quota, and rate limits."""
        headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "x-api-token": self._token,
        }
        body = self._request("GET", ACCOUNT_URL, headers=headers, timeout=timeout)
        details = body.get("data", body) if isinstance(body, dict) else body
        if not isinstance(details, dict):
            raise MrscraperAPIError("Account response must contain an object.")
        token_limit = _number_or_zero(details.get("tokenLimit"))
        token_usage = _number_or_zero(details.get("tokenUsage"))
        user = details.get("user")
        if not isinstance(user, dict):
            user = {}
        return {
            "subscription_status": _string_or_none(details.get("stripeStatus")),
            "enterprise": bool(details.get("isEnterprise")),
            "token_usage": token_usage,
            "token_limit": token_limit,
            "token_remaining": max(0, token_limit - token_usage),
            "usage_percent": round(token_usage / token_limit * 100, 2) if token_limit > 0 else 0,
            "rate_limit": _number_or_zero(details.get("rateLimit")),
            "rate_ttl": _number_or_zero(details.get("rateTtl")),
            "auto_renew": bool(details.get("isAutoRenew")),
            "ends_at": _string_or_none(details.get("endsAt")),
            "user": {
                "name": _string_or_none(user.get("name")),
                "email": _string_or_none(user.get("email")),
                "verified": bool(user.get("isVerified")),
            },
        }

    def scraper_api(
        self,
        *,
        url: str,
        html: bool = True,
        markdown: bool = False,
        screenshot: bool = False,
        timeout: int = 120,
        geo_code: str = "US",
        proxy_country: str | None = None,
        browser_rendering: bool | None = None,
        super: bool = False,
        use_proxy: bool = True,
        proxy: str | None = None,
        wait_for_selector: str | None = None,
        wait_until: str | None = None,
        home_page: bool = False,
        block_resources: bool = False,
        bypass_proxy: bool = False,
        cookie_jar: str | None = None,
        headers: dict[str, str] | None = None,
        max_retries: int = 3,
        token_cap: int | None = None,
        stream: bool | None = None,
        discard_token_secret: str | None = None,
    ) -> Any:
        """Fetch a page with GET; the target URL and every option go in the query string."""
        if not (html or markdown or screenshot):
            raise ValueError("At least one of html, markdown, or screenshot must be true.")
        query = _compact(
            {
                "token": self._token,
                "url": url,
                "html": html,
                "markdown": markdown,
                "screenshot": True if screenshot else None,
                "timeout": timeout,
                "geoCode": geo_code,
                "proxyCountry": proxy_country,
                "browserRendering": True if screenshot else browser_rendering,
                "super": True if super else None,
                "useProxy": None if use_proxy else False,
                "proxy": proxy,
                "waitForSelector": wait_for_selector,
                "waitUntil": wait_until,
                "warmStart": True if home_page else None,
                "blockResources": True if block_resources else None,
                "bypassProxy": True if bypass_proxy else None,
                "cookieJar": cookie_jar,
                "headers": json.dumps(headers) if headers is not None else None,
                "stream": stream,
                "maxRetries": max_retries,
                "tokenCap": token_cap,
            }
        )
        encoded = {
            key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in query.items()
        }
        request_headers = {"x-api-token": self._token}
        if discard_token_secret:
            request_headers["x-discard-token-secret"] = discard_token_secret
        return self._request(
            "GET",
            f"{API_URL}?{urlencode(encoded)}",
            headers=request_headers,
            timeout=float(timeout + 30),
        )

    def web_search(
        self,
        *,
        query: str,
        country: str | None = None,
        num_results: int = 10,
    ) -> Any:
        """Run a web search through a JSON POST with the websearch action."""
        payload = _compact(
            {
                "action": "websearch",
                "query": query,
                "country": country,
                "numResults": num_results,
            }
        )
        return self._request(
            "POST",
            API_URL,
            headers={"x-api-token": self._token, "Content-Type": "application/json"},
            payload=payload,
            timeout=WEB_SEARCH_TIMEOUT,
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        with httpx.Client(transport=self.transport, timeout=timeout) as client:
            response = client.request(
                method,
                url,
                headers=headers,
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
