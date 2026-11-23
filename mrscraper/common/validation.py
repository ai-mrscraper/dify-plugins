from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import urlsplit


class ParameterValidationError(ValueError):
    """Raised when public tool parameters violate the operation contract."""


def nonblank_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ParameterValidationError(f"{name} must be a nonblank string.")
    return value.strip()


def optional_string(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ParameterValidationError(f"{name} must be a string.")
    stripped = value.strip()
    return stripped or None


def web_url(value: Any, name: str = "url") -> str:
    result = nonblank_string(value, name)
    try:
        parsed = urlsplit(result)
        valid = parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)
    except ValueError:
        valid = False
    if not valid:
        raise ParameterValidationError(f"{name} must be an absolute HTTP or HTTPS URL.")
    return result


def integer(
    value: Any,
    name: str,
    *,
    default: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    candidate = default if value is None or value == "" else value
    if isinstance(candidate, bool) or not isinstance(candidate, int | float):
        raise ParameterValidationError(f"{name} must be an integer.")
    if isinstance(candidate, float) and (
        not math.isfinite(candidate) or not candidate.is_integer()
    ):
        raise ParameterValidationError(f"{name} must be an integer.")
    result = int(candidate)
    if minimum is not None and result < minimum:
        raise ParameterValidationError(f"{name} must be at least {minimum}.")
    if maximum is not None and result > maximum:
        raise ParameterValidationError(f"{name} must be at most {maximum}.")
    return result


def optional_integer(value: Any, name: str, *, minimum: int | None = None) -> int | None:
    if value is None or value == "":
        return None
    return integer(value, name, minimum=minimum)


def boolean(value: Any, name: str, *, default: bool) -> bool:
    candidate = default if value is None else value
    if not isinstance(candidate, bool):
        raise ParameterValidationError(f"{name} must be a boolean.")
    return candidate


def choice(value: Any, name: str, allowed: set[str], *, default: str | None = None) -> str:
    candidate = default if value is None else value
    if not isinstance(candidate, str) or candidate not in allowed:
        values = ", ".join(sorted(allowed))
        raise ParameterValidationError(f"{name} must be one of: {values}.")
    return candidate


def optional_country_code(value: Any, name: str) -> str | None:
    """Return a lowercase two-letter code, or None when the input is empty."""
    candidate = optional_string(value, name)
    if candidate is None:
        return None
    if len(candidate) != 2 or not candidate.isascii() or not candidate.isalpha():
        raise ParameterValidationError(f"{name} must be a two-letter country code.")
    return candidate.lower()


def optional_bounded_string(value: Any, name: str, *, max_length: int) -> str | None:
    result = optional_string(value, name)
    if result is not None and len(result) > max_length:
        raise ParameterValidationError(f"{name} must be at most {max_length} characters.")
    return result


def optional_tristate(value: Any, name: str) -> bool | None:
    """Map auto or an empty input to None (omitted), and true/false to booleans."""
    if value is None or value == "" or value == "auto":
        return None
    if isinstance(value, bool):
        return value
    if value in {"true", "false"}:
        return value == "true"
    raise ParameterValidationError(f"{name} must be auto, true, or false.")


_VIEWPORT = re.compile(r"^(\d{3,4})x(\d{3,4})(?:-(\d{2,3}))?$")


def screenshot_capture(value: Any, name: str) -> str | bool:
    """Accept false (or an empty input), full, top, or WIDTHxHEIGHT with an optional -ZOOM."""
    if value is None or value is False or value in {"", "false"}:
        return False
    if value in {"full", "top"}:
        return value
    match = _VIEWPORT.match(value) if isinstance(value, str) else None
    if match:
        width, height = int(match[1]), int(match[2])
        zoom = 100 if match[3] is None else int(match[3])
        if 100 <= width <= 3840 and 100 <= height <= 3840 and 25 <= zoom <= 300:
            return value
    raise ParameterValidationError(
        f"{name} must be false, full, top, or WIDTHxHEIGHT from 100 to 3840 pixels with an "
        "optional -ZOOM from 25 to 300, such as 1280x800 or 1920x1080-75."
    )
