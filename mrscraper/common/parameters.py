"""Validate Dify tool inputs and normalize them to client keyword arguments.

Unset values (``None`` or blank strings) take the documented defaults or stay
omitted. Every check runs before an HTTP request is made.
"""

from __future__ import annotations

from typing import Any

from common.client import DEFAULT_JSON_PROMPT
from common.validation import (
    ParameterValidationError,
    boolean,
    integer,
    nonblank_string,
    optional_bounded_string,
    optional_country_code,
    optional_integer,
    optional_string,
    optional_tristate,
    screenshot_area,
    screenshot_capture,
    web_url,
)

MAX_TIMEOUT = 330
MAX_SELECTOR_LENGTH = 500
MAX_CACHE_AGE_MS = 604_800_000
MAX_QUERY_LENGTH = 1000
MIN_SEARCH_RESULTS = 10
MAX_SEARCH_RESULTS = 100


def _flag(parameters: dict[str, Any], name: str, default: bool) -> bool:
    return boolean(parameters.get(name), name, default=default)


def _page(parameters: dict[str, Any]) -> dict[str, Any]:
    """Page controls shared by HTML, Markdown, screenshots, and JSON extraction."""
    result: dict[str, Any] = {
        "url": web_url(parameters.get("url")),
        "timeout": integer(
            parameters.get("timeout"), "timeout", default=300, minimum=1, maximum=MAX_TIMEOUT
        ),
        "max_age": integer(
            parameters.get("max_age"), "max_age", default=0, minimum=0, maximum=MAX_CACHE_AGE_MS
        ),
    }
    optional = {
        "wait_for_selector": optional_bounded_string(
            parameters.get("wait_for_selector"), "wait_for_selector", max_length=MAX_SELECTOR_LENGTH
        ),
        "geo_code": optional_country_code(parameters.get("geo_code"), "geo_code"),
        "max_retries": optional_integer(parameters.get("max_retries"), "max_retries", minimum=0),
    }
    return result | {name: value for name, value in optional.items() if value is not None}


def _loading(parameters: dict[str, Any]) -> dict[str, Any]:
    """Page controls plus the loading controls used by HTML, Markdown, and JSON extraction."""
    result = _page(parameters) | {
        "warm_start": _flag(parameters, "warm_start", False),
        "block_resources": _flag(parameters, "block_resources", False),
    }
    browser_rendering = optional_tristate(parameters.get("browser_rendering"), "browser_rendering")
    if browser_rendering is not None:
        result["browser_rendering"] = browser_rendering
    return result


def _with_action(parameters: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    action = optional_string(parameters.get("action"), "action")
    return result | ({"action": action} if action is not None else {})


def status_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return {}


def scrape_html_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    result = _with_action(parameters, _loading(parameters))
    capture = screenshot_capture(parameters.get("screenshot"), "screenshot")
    if capture is not False:
        # A screenshot needs a rendered page, so it always sends browserRendering=true.
        result["browser_rendering"] = True
    return result | {"screenshot": capture}


def scrape_markdown_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return _with_action(parameters, _loading(parameters))


def get_screenshot_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return _page(parameters) | {
        "screenshot": screenshot_area(parameters.get("screenshot"), "screenshot")
    }


def scrape_brand_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return {"url": web_url(parameters.get("url"))}


def scrape_json_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    prompt = parameters.get("prompt")
    if prompt is None or prompt == "":
        prompt = DEFAULT_JSON_PROMPT
    nonblank_string(prompt, "prompt")
    return _loading(parameters) | {
        "prompt": prompt,
        "html": _flag(parameters, "html", True),
        "screenshot": _flag(parameters, "screenshot", False),
    }


def web_search_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    query = nonblank_string(parameters.get("query"), "query")
    if len(query) > MAX_QUERY_LENGTH:
        raise ParameterValidationError(f"query must be 1 to {MAX_QUERY_LENGTH} characters.")
    result: dict[str, Any] = {
        "query": query,
        "num_results": integer(
            parameters.get("num_results"),
            "num_results",
            default=MIN_SEARCH_RESULTS,
            minimum=MIN_SEARCH_RESULTS,
            maximum=MAX_SEARCH_RESULTS,
        ),
    }
    country = optional_country_code(parameters.get("country"), "country")
    if country is not None:
        result["country"] = country
    return result


PARAMETERS = {
    "status": status_parameters,
    "scrape_html": scrape_html_parameters,
    "scrape_markdown": scrape_markdown_parameters,
    "get_screenshot": get_screenshot_parameters,
    "scrape_brand": scrape_brand_parameters,
    "scrape_json": scrape_json_parameters,
    "web_search": web_search_parameters,
}
