from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import quote, quote_plus

from gevent.threadpool import ThreadPoolExecutor
from mrscraper import MrScraper
from mrscraper.exceptions import MrScraperError


class MrscraperAPIError(RuntimeError):
    """A safe, user-facing SDK error."""


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


class MrscraperClient:
    def __init__(self, token: str) -> None:
        if not isinstance(token, str) or not token.strip():
            raise MrscraperAPIError("MrScraper API token is required.")
        self._token = token.strip()

    def invoke(self, operation: str, parameters: dict[str, Any]) -> Any:
        if operation not in {"account", "scraper_api", "web_search"}:
            raise ValueError("Unsupported MrScraper operation.")

        async def request() -> Any:
            client = MrScraper(token=self._token)
            result = await getattr(client, operation)(**parameters)
            return result["data"]

        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(request())
            # Dify patches standard threads with gevent. Use a native thread
            # when an async caller already owns this thread's event loop.
            with ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(lambda: asyncio.run(request())).result()
        except (MrScraperError, ValueError) as exc:
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
            raise MrscraperAPIError(sanitize_error(str(exc), secrets)) from None
