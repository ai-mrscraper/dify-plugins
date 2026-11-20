"""Validate Dify tool inputs and normalize them to client keyword arguments.

Unset values (``None`` or blank strings) take the standard service defaults. Every
check runs before an HTTP request is made.
"""

from __future__ import annotations

from typing import Any

from common.client import DEFAULT_JSON_PROMPT
from common.validation import (
    ParameterValidationError,
    boolean,
    choice,
    country_code,
    integer,
    nonblank_string,
    optional_integer,
    optional_string,
    web_url,
)

WAIT_UNTIL_EVENTS = {"domcontentloaded", "load", "networkidle0", "networkidle2"}
SCREENSHOT_AREAS = {"full", "top"}
MAX_QUERY_LENGTH = 1000
MIN_SEARCH_RESULTS = 10
MAX_SEARCH_RESULTS = 100


def _flag(parameters: dict[str, Any], name: str, default: bool) -> bool:
    return boolean(parameters.get(name), name, default=default)


def _select(parameters: dict[str, Any], name: str, allowed: set[str], default: str) -> str:
    value = parameters.get(name)
    return choice(None if value == "" else value, name, allowed, default=default)


def _page(parameters: dict[str, Any]) -> dict[str, Any]:
    """Page controls shared by HTML, Markdown, screenshots, and JSON extraction."""
    result: dict[str, Any] = {
        "url": web_url(parameters.get("url")),
        "timeout": integer(
            parameters.get("timeout"), "timeout", default=300, minimum=1, maximum=300
        ),
        "geo_code": country_code(parameters.get("geo_code"), "geo_code", default="us"),
        "proxy_country": country_code(
            parameters.get("proxy_country"), "proxy_country", default="us"
        ),
        "super": _flag(parameters, "super", False),
        "wait_until": _select(parameters, "wait_until", WAIT_UNTIL_EVENTS, "domcontentloaded"),
        "save_result": _flag(parameters, "save_result", False),
    }
    proxy = optional_string(parameters.get("proxy"), "proxy")
    if proxy is not None:
        result["proxy"] = proxy
    max_retries = optional_integer(parameters.get("max_retries"), "max_retries", minimum=0)
    if max_retries is not None:
        result["max_retries"] = max_retries
    return result


def _loading(parameters: dict[str, Any]) -> dict[str, Any]:
    """Page controls plus the loading controls used by HTML, Markdown, and screenshots."""
    result = _page(parameters)
    result["block_resources"] = _flag(parameters, "block_resources", False)
    selector = optional_string(parameters.get("wait_for_selector"), "wait_for_selector")
    if selector is not None:
        result["wait_for_selector"] = selector
    result["return_cookie"] = _flag(parameters, "return_cookie", False)
    return result


def status_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return {}


def scrape_html_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return _loading(parameters) | {
        "browser_rendering": _flag(parameters, "browser_rendering", False),
        "warm_start": _flag(parameters, "warm_start", False),
    }


def scrape_markdown_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return scrape_html_parameters(parameters) | {"html": _flag(parameters, "html", False)}


def get_screenshot_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return _loading(parameters) | {
        "warm_start": _flag(parameters, "warm_start", False),
        "screenshot": _select(parameters, "screenshot", SCREENSHOT_AREAS, "full"),
        "html": _flag(parameters, "html", True),
        "markdown": _flag(parameters, "markdown", False),
    }


def scrape_brand_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return {"url": web_url(parameters.get("url"))}


def scrape_json_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    prompt = parameters.get("prompt")
    if prompt is None or prompt == "":
        prompt = DEFAULT_JSON_PROMPT
    nonblank_string(prompt, "prompt")
    return _page(parameters) | {
        "prompt": prompt,
        "browser_rendering": _flag(parameters, "browser_rendering", False),
        "html": _flag(parameters, "html", False),
        "screenshot": _flag(parameters, "screenshot", False),
    }


def web_search_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    query = nonblank_string(parameters.get("query"), "query")
    if len(query) > MAX_QUERY_LENGTH:
        raise ParameterValidationError(f"query must be 1 to {MAX_QUERY_LENGTH} characters.")
    return {
        "query": query,
        "country": country_code(parameters.get("country"), "country", default="us"),
        "num_results": integer(
            parameters.get("num_results"),
            "num_results",
            default=MIN_SEARCH_RESULTS,
            minimum=MIN_SEARCH_RESULTS,
            maximum=MAX_SEARCH_RESULTS,
        ),
    }


PARAMETERS = {
    "status": status_parameters,
    "scrape_html": scrape_html_parameters,
    "scrape_markdown": scrape_markdown_parameters,
    "get_screenshot": get_screenshot_parameters,
    "scrape_brand": scrape_brand_parameters,
    "scrape_json": scrape_json_parameters,
    "web_search": web_search_parameters,
}
