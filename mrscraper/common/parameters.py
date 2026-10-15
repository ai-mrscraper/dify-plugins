from __future__ import annotations

import math
from typing import Any

from common.validation import (
    ParameterValidationError,
    boolean,
    choice,
    integer,
    json_object,
    nonblank_string,
    optional_integer,
    optional_string,
    web_url,
)


def seconds(value: Any, default: float) -> float:
    candidate = default if value is None else value
    if (
        isinstance(candidate, bool)
        or not isinstance(candidate, int | float)
        or not math.isfinite(candidate)
        or candidate <= 0
    ):
        raise ParameterValidationError("timeout must be a positive finite number of seconds.")
    return float(candidate)


def tristate(value: Any, name: str) -> bool | None:
    if value is None or value == "auto":
        return None
    if isinstance(value, bool):
        return value
    normalized = choice(value, name, {"true", "false"})
    return normalized == "true"


def account_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return {"timeout": seconds(parameters.get("timeout"), 30)}


def scraper_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"url": web_url(parameters.get("url"))}
    for name, default in {
        "html": True,
        "markdown": False,
        "block_resources": False,
        "super": False,
        "use_proxy": True,
        "home_page": False,
        "screenshot": False,
        "bypass_proxy": False,
    }.items():
        if name in parameters:
            result[name] = boolean(parameters[name], name, default=default)
    for name in ("browser_rendering", "stream"):
        if name in parameters:
            result[name] = tristate(parameters[name], name)
    for name in (
        "geo_code",
        "proxy_country",
        "proxy",
        "wait_for_selector",
        "cookie_jar",
        "discard_token_secret",
    ):
        if name in parameters:
            value = optional_string(parameters[name], name)
            if value is not None:
                result[name] = value
    if "timeout" in parameters:
        timeout = integer(parameters["timeout"], "timeout", default=120, minimum=1)
        if timeout > 300:
            raise ParameterValidationError("timeout must be between 1 and 300 seconds.")
        result["timeout"] = timeout
    if "max_retries" in parameters:
        result["max_retries"] = integer(
            parameters["max_retries"], "max_retries", default=3, minimum=0
        )
    if "token_cap" in parameters:
        result["token_cap"] = optional_integer(parameters["token_cap"], "token_cap", minimum=0)
    if "headers" in parameters:
        headers = json_object(parameters["headers"], "headers")
        if headers is not None and any(not isinstance(value, str) for value in headers.values()):
            raise ParameterValidationError("headers values must be strings.")
        result["headers"] = headers
    return result


def search_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"url": nonblank_string(parameters.get("url"), "url")}
    for name, default in (("raw", True), ("render_js", False)):
        if name in parameters:
            result[name] = boolean(parameters[name], name, default=default)
    for name in ("region", "language"):
        if name in parameters:
            result[name] = optional_string(parameters[name], name)
    if "page" in parameters:
        result["page"] = optional_integer(parameters["page"], "page", minimum=1)
    if "format" in parameters:
        result["format"] = choice(parameters["format"], "format", {"json", "html"}, default="json")
    result["timeout"] = seconds(parameters.get("timeout"), 600)
    return result
