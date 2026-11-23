import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, quote_plus, urlsplit

import httpx
import pytest
import yaml
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from common.client import MrscraperAPIError, MrscraperClient
from common.parameters import PARAMETERS
from common.validation import ParameterValidationError
from provider.mrscraper import MrscraperProvider
from tools.mrscraper_get_screenshot import MrscraperGetScreenshotTool
from tools.mrscraper_scrape_brand import MrscraperScrapeBrandTool
from tools.mrscraper_scrape_html import MrscraperScrapeHtmlTool
from tools.mrscraper_scrape_json import MrscraperScrapeJsonTool
from tools.mrscraper_scrape_markdown import MrscraperScrapeMarkdownTool
from tools.mrscraper_status import MrscraperStatusTool
from tools.mrscraper_web_search import MrscraperWebSearchTool

ROOT = Path(__file__).parents[1]
TOKEN = "test-api-token+secret"
URL = "https://example.com"
TOOLS = {
    "status": MrscraperStatusTool,
    "scrape_html": MrscraperScrapeHtmlTool,
    "scrape_markdown": MrscraperScrapeMarkdownTool,
    "get_screenshot": MrscraperGetScreenshotTool,
    "scrape_brand": MrscraperScrapeBrandTool,
    "scrape_json": MrscraperScrapeJsonTool,
    "web_search": MrscraperWebSearchTool,
}
SHARED_DEFAULT_QUERY = {"timeout": "300", "saveResult": "true", "maxAge": "0"}
LOADING_DEFAULT_QUERY = {"warmStart": "false", "blockResources": "false"}
# Options from earlier releases that the Scraper API reference no longer lists.
REMOVED = {
    "super": True,
    "wait_until": "load",
    "proxy_country": "sg",
    "proxy": "http://proxy.example.com:8080",
    "return_cookie": True,
    "markdown": True,
}
REMOVED_WIRE = {"super", "waitUntil", "proxyCountry", "proxy", "returnCookie", "markdown"}


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch):
    """Serve plugin HTTP requests from an in-memory handler."""
    requests: list[httpx.Request] = []

    def default(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": ["result"]})

    responder: Callable[[httpx.Request], httpx.Response] = default

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return responder(request)

    def configure(handler: Callable[[httpx.Request], httpx.Response]) -> list[httpx.Request]:
        nonlocal responder
        responder = handler
        return requests

    monkeypatch.setattr(MrscraperClient, "transport", httpx.MockTransport(handle))
    yield configure, requests


def _invoke(operation: str, parameters: dict[str, Any]) -> list:
    return list(TOOLS[operation].from_credentials({"api_token": TOKEN})._invoke(parameters))


def _query(request: httpx.Request) -> dict[str, str]:
    return dict(request.url.params)


def _assert_authenticated(request: httpx.Request, timeout: float) -> None:
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert request.headers["x-api-token"] == TOKEN
    assert request.headers["accept"] == "application/json"
    assert "token" not in request.url.params
    assert TOKEN not in str(request.url)
    assert request.extensions["timeout"]["read"] == timeout


def test_status_returns_the_raw_account_body_unchanged(transport) -> None:
    configure, requests = transport
    body = {
        "message": "Example response",
        "data": {
            "id": "ACCOUNT_ID",
            "tokenLimit": 100000,
            "tokenUsage": 2500,
            "stripeStatus": "active",
            "user": {"name": "Example user", "email": "user@example.com", "isVerified": True},
            "subscriptionItem": {"name": "Example plan", "tokenLimit": 100000},
            "scraperAllowance": {"remaining": 97500, "plans": [{"remaining": 97500}]},
        },
    }
    configure(
        lambda request: httpx.Response(
            200, json=body, headers={"set-cookie": "session=response-secret"}
        )
    )

    messages = _invoke("status", {})

    assert len(messages) == 1
    assert messages[0].type.value == "json"
    assert messages[0].message.json_object == body
    assert "response-secret" not in messages[0].model_dump_json()
    request = requests[0]
    assert request.method == "GET"
    assert str(request.url) == "https://api.app.mrscraper.com/api/v1/subscription-accounts"
    assert request.content == b""
    _assert_authenticated(request, 600)


def test_scrape_html_defaults_send_the_full_get_query_and_emit_text(transport) -> None:
    configure, requests = transport
    configure(
        lambda request: httpx.Response(
            200, text="<html>Example</html>", headers={"content-type": "text/html"}
        )
    )

    messages = _invoke("scrape_html", {"url": f" {URL} "})

    assert [message.type.value for message in messages] == ["text"]
    assert messages[0].message.text == "<html>Example</html>"
    request = requests[0]
    assert request.method == "GET"
    assert request.content == b""
    assert str(request.url.copy_with(query=None)) == "https://api.mrscraper.com"
    query = _query(request)
    assert query == {
        "url": URL,
        "html": "true",
        **SHARED_DEFAULT_QUERY,
        **LOADING_DEFAULT_QUERY,
        "screenshot": "false",
    }
    assert list(query) == [
        "url",
        "html",
        "timeout",
        "warmStart",
        "blockResources",
        "saveResult",
        "maxAge",
        "screenshot",
    ]
    _assert_authenticated(request, 330)


def test_scrape_html_sends_every_documented_control_in_order(transport) -> None:
    _, requests = transport

    _invoke(
        "scrape_html",
        {
            "url": URL,
            # A screenshot overrides this and sends browserRendering=true.
            "browser_rendering": "false",
            "timeout": 120.0,
            "warm_start": True,
            "block_resources": True,
            "wait_for_selector": " body ",
            "action": " product-flow ",
            "geo_code": "ID",
            "save_result": False,
            "max_age": 3600000,
            "token_cap": 50,
            "max_retries": 0,
            "screenshot": "1920x1080-75",
            **REMOVED,
        },
    )

    request = requests[0]
    query = _query(request)
    assert list(query.items()) == [
        ("url", URL),
        ("html", "true"),
        ("browserRendering", "true"),
        ("timeout", "120"),
        ("warmStart", "true"),
        ("blockResources", "true"),
        ("waitForSelector", "body"),
        ("action", "product-flow"),
        ("geoCode", "id"),
        ("saveResult", "false"),
        ("maxAge", "3600000"),
        ("tokenCap", "50"),
        ("maxRetries", "0"),
        ("screenshot", "1920x1080-75"),
    ]
    _assert_authenticated(request, 150)


@pytest.mark.parametrize(
    ("value", "sent"),
    [
        (None, None),
        ("", None),
        ("auto", None),
        ("true", "true"),
        ("false", "false"),
        (True, "true"),
        (False, "false"),
    ],
)
@pytest.mark.parametrize("operation", ["scrape_html", "scrape_markdown", "scrape_json"])
def test_browser_rendering_is_omitted_unless_set(transport, operation, value, sent) -> None:
    _, requests = transport

    _invoke(operation, {"url": URL, "browser_rendering": value})

    assert _query(requests[0]).get("browserRendering") == sent


@pytest.mark.parametrize(
    ("value", "sent"),
    [
        (None, "false"),
        ("", "false"),
        ("false", "false"),
        (False, "false"),
        ("full", "full"),
        ("top", "top"),
        ("100x100", "100x100"),
        ("3840x3840-300", "3840x3840-300"),
        ("1280x800-25", "1280x800-25"),
    ],
)
def test_scrape_html_screenshot_accepts_documented_captures(transport, value, sent) -> None:
    _, requests = transport

    _invoke("scrape_html", {"url": URL, "screenshot": value})

    query = _query(requests[0])
    assert query["screenshot"] == sent
    # Any screenshot sends browserRendering=true; none leaves rendering omitted.
    assert query.get("browserRendering") == (None if sent == "false" else "true")


@pytest.mark.parametrize("rendering", [None, "", "auto", "true", "false", True, False])
@pytest.mark.parametrize("capture", ["full", "top", "1280x800-75"])
def test_scrape_html_screenshot_always_sends_browser_rendering(
    transport, capture, rendering
) -> None:
    _, requests = transport

    _invoke("scrape_html", {"url": URL, "screenshot": capture, "browser_rendering": rendering})

    query = _query(requests[0])
    assert query["browserRendering"] == "true"
    assert list(query)[:3] == ["url", "html", "browserRendering"]
    assert query["screenshot"] == capture


@pytest.mark.parametrize(
    ("rendering", "sent"), [(None, None), ("auto", None), ("true", "true"), ("false", "false")]
)
def test_scrape_html_without_screenshot_keeps_browser_rendering_input(
    transport, rendering, sent
) -> None:
    _, requests = transport

    _invoke("scrape_html", {"url": URL, "screenshot": "false", "browser_rendering": rendering})

    assert _query(requests[0]).get("browserRendering") == sent


def test_invalid_browser_rendering_is_rejected_even_with_a_screenshot(transport) -> None:
    _, requests = transport

    with pytest.raises(ParameterValidationError):
        _invoke("scrape_html", {"url": URL, "screenshot": "top", "browser_rendering": "maybe"})

    assert requests == []


def test_scrape_json_screenshot_does_not_force_browser_rendering(transport) -> None:
    _, requests = transport

    _invoke("scrape_json", {"url": URL, "screenshot": True})

    query = _query(requests[0])
    assert query["screenshot"] == "true"
    assert "browserRendering" not in query


def test_scrape_markdown_defaults_return_markdown_text(transport) -> None:
    configure, requests = transport
    configure(
        lambda request: httpx.Response(
            200, text="# Example page", headers={"content-type": "text/markdown; charset=utf-8"}
        )
    )

    messages = _invoke("scrape_markdown", {"url": URL, "html": True, "screenshot": "top"})

    assert messages[0].message.text == "# Example page"
    request = requests[0]
    assert _query(request) == {
        "url": URL,
        "markdown": "true",
        **SHARED_DEFAULT_QUERY,
        **LOADING_DEFAULT_QUERY,
    }
    _assert_authenticated(request, 330)


def test_scrape_markdown_sends_rendering_action_and_cache_controls(transport) -> None:
    _, requests = transport

    _invoke(
        "scrape_markdown",
        {
            "url": URL,
            "browser_rendering": "true",
            "action": "docs",
            "max_age": 86400000,
            "token_cap": 5,
            "geo_code": "gb",
        },
    )

    assert list(_query(requests[0]).items()) == [
        ("url", URL),
        ("markdown", "true"),
        ("browserRendering", "true"),
        ("timeout", "300"),
        ("warmStart", "false"),
        ("blockResources", "false"),
        ("action", "docs"),
        ("geoCode", "gb"),
        ("saveResult", "true"),
        ("maxAge", "86400000"),
        ("tokenCap", "5"),
    ]


def test_get_screenshot_always_sends_a_full_page_rendered_capture(transport) -> None:
    configure, requests = transport
    body = {"html": "<html>...</html>", "screenshot": "BASE64_PNG_DATA"}
    configure(lambda request: httpx.Response(200, json=body))

    messages = _invoke("get_screenshot", {"url": URL})

    assert messages[0].message.json_object == body
    request = requests[0]
    assert request.method == "GET"
    assert list(_query(request).items()) == [
        ("url", URL),
        ("screenshot", "full"),
        ("browserRendering", "true"),
        ("timeout", "300"),
        ("saveResult", "true"),
        ("maxAge", "0"),
    ]
    _assert_authenticated(request, 330)


def test_get_screenshot_sends_its_documented_controls_only(transport) -> None:
    _, requests = transport

    _invoke(
        "get_screenshot",
        {
            "url": URL,
            "timeout": 120,
            "wait_for_selector": "#results",
            "geo_code": "DE",
            "save_result": False,
            "max_age": 0,
            "token_cap": 10,
            "max_retries": 1,
            # Not Get screenshot inputs: the area and rendering are fixed.
            "screenshot": "top",
            "browser_rendering": "false",
            "warm_start": True,
            "block_resources": True,
            "html": False,
            "action": "flow",
            **REMOVED,
        },
    )

    assert list(_query(requests[0]).items()) == [
        ("url", URL),
        ("screenshot", "full"),
        ("browserRendering", "true"),
        ("timeout", "120"),
        ("waitForSelector", "#results"),
        ("geoCode", "de"),
        ("saveResult", "false"),
        ("maxAge", "0"),
        ("tokenCap", "10"),
        ("maxRetries", "1"),
    ]


def test_scrape_brand_requests_the_brand_action_only(transport) -> None:
    configure, requests = transport
    body = {"data": {"status": "succeeded", "brand": {"name": "Example brand"}}}
    configure(lambda request: httpx.Response(200, json=body))

    messages = _invoke(
        "scrape_brand", {"url": URL, "timeout": 5, "warm_start": True, "max_age": 3600000}
    )

    assert messages[0].message.json_object == body
    request = requests[0]
    assert request.method == "GET"
    assert _query(request) == {"action": "brand-scraping", "url": URL, "bundle": "none"}
    _assert_authenticated(request, 120)


def test_scrape_json_defaults_use_the_general_agent_and_include_html(transport) -> None:
    configure, requests = transport
    body = {
        "success": True,
        "data": [{"title": "Example item"}],
        "html": "<html>",
        "screenshot": "",
    }
    configure(lambda request: httpx.Response(200, json=body))

    messages = _invoke("scrape_json", {"url": URL, "prompt": None})

    assert messages[0].message.json_object == body
    request = requests[0]
    assert request.method == "GET"
    assert request.content == b""
    assert list(_query(request).items()) == [
        ("url", URL),
        ("prompt", "Extract all data as complete as possible."),
        ("agent", "general"),
        ("html", "true"),
        ("timeout", "300"),
        ("warmStart", "false"),
        ("blockResources", "false"),
        ("saveResult", "true"),
        ("maxAge", "0"),
        ("screenshot", "false"),
    ]
    _assert_authenticated(request, 330)


def test_scrape_json_sends_loading_controls_and_boolean_screenshot(transport) -> None:
    _, requests = transport

    _invoke(
        "scrape_json",
        {
            "url": URL,
            "prompt": 'Extract the title. Json Schema: {"type":"object"}',
            "html": False,
            "browser_rendering": "true",
            "warm_start": True,
            "block_resources": True,
            "wait_for_selector": "body",
            "geo_code": "SG",
            "max_age": 60000,
            "token_cap": 20,
            "max_retries": 2,
            "screenshot": True,
            "action": "ignored",
            **REMOVED,
        },
    )

    assert list(_query(requests[0]).items()) == [
        ("url", URL),
        ("prompt", 'Extract the title. Json Schema: {"type":"object"}'),
        ("agent", "general"),
        ("html", "false"),
        ("browserRendering", "true"),
        ("timeout", "300"),
        ("warmStart", "true"),
        ("blockResources", "true"),
        ("waitForSelector", "body"),
        ("geoCode", "sg"),
        ("saveResult", "true"),
        ("maxAge", "60000"),
        ("tokenCap", "20"),
        ("maxRetries", "2"),
        ("screenshot", "true"),
    ]


def test_scrape_json_switches_to_post_above_eight_thousand_characters(transport) -> None:
    _, requests = transport
    prompt = "Extract every product. " + "x" * 8000

    _invoke("scrape_json", {"url": URL, "prompt": prompt, "timeout": 60})

    request = requests[0]
    assert request.method == "POST"
    assert json.loads(request.content) == {"url": URL, "prompt": prompt, "agent": "general"}
    query = _query(request)
    for name in ("url", "prompt", "agent"):
        assert name not in query
    assert query["timeout"] == "60"
    assert query["html"] == "true"
    assert query["screenshot"] == "false"
    assert len(str(request.url)) <= 8000
    _assert_authenticated(request, 90)


def test_scrape_json_stays_get_at_the_url_length_limit(transport) -> None:
    _, requests = transport
    _invoke("scrape_json", {"url": URL, "prompt": "x"})
    prompt = "x" * (8000 - len(str(requests[0].url)) + 1)

    _invoke("scrape_json", {"url": URL, "prompt": prompt})
    assert requests[-1].method == "GET"
    assert len(str(requests[-1].url)) == 8000

    _invoke("scrape_json", {"url": URL, "prompt": prompt + "x"})
    assert requests[-1].method == "POST"


def test_web_search_sends_a_get_websearch_action(transport) -> None:
    configure, requests = transport
    body = {
        "success": True,
        "message": "Example response",
        "data": [
            {
                "rank": 1,
                "title": "Example result",
                "url": URL,
                "description": "Example result description.",
                "source": "example.com",
            }
        ],
        "tokenUsage": 1,
    }
    configure(lambda request: httpx.Response(200, json=body))

    messages = _invoke(
        "web_search",
        {"query": " site:example.com documentation ", "country": "ID", "num_results": 20},
    )

    assert messages[0].message.json_object == body
    request = requests[0]
    assert request.method == "GET"
    assert request.content == b""
    assert str(request.url.copy_with(query=None)) == "https://api.mrscraper.com"
    assert list(_query(request).items()) == [
        ("action", "websearch"),
        ("query", "site:example.com documentation"),
        ("country", "id"),
        ("numResults", "20"),
    ]
    _assert_authenticated(request, 120)


def test_web_search_omits_country_unless_set_and_defaults_to_ten_results(transport) -> None:
    _, requests = transport

    _invoke("web_search", {"query": "example domain", "country": " ", "num_results": None})

    assert _query(requests[0]) == {
        "action": "websearch",
        "query": "example domain",
        "numResults": "10",
    }


@pytest.mark.parametrize("operation", ["scrape_html", "scrape_markdown", "scrape_json"])
def test_removed_options_never_reach_the_wire(transport, operation: str) -> None:
    _, requests = transport

    _invoke(operation, {"url": URL, **REMOVED})

    query = _query(requests[0])
    # markdown=true is Scrape Markdown's fixed field; it is never an input.
    fixed = {"markdown"} if operation == "scrape_markdown" else set()
    assert (REMOVED_WIRE - fixed).isdisjoint(query)
    if fixed:
        assert query["markdown"] == "true"


def _sample_value(parameter: dict) -> Any:
    name = parameter["name"]
    if parameter["type"] == "boolean":
        return not parameter.get("default", False)
    if parameter["type"] == "select":
        return parameter["options"][-1]["value"]
    if parameter["type"] == "number":
        return {
            "timeout": 45,
            "max_age": 3600000,
            "token_cap": 7,
            "max_retries": 4,
            "num_results": 30,
        }[name]
    return {
        "url": "https://example.com/changed",
        "wait_for_selector": "main",
        "action": "flow",
        "geo_code": "de",
        "screenshot": "top",
        "prompt": "Extract the heading.",
        "query": "changed query",
        "country": "gb",
    }[name]


WIRE_NAMES = {
    "browser_rendering": "browserRendering",
    "warm_start": "warmStart",
    "block_resources": "blockResources",
    "wait_for_selector": "waitForSelector",
    "geo_code": "geoCode",
    "save_result": "saveResult",
    "max_age": "maxAge",
    "token_cap": "tokenCap",
    "max_retries": "maxRetries",
    "num_results": "numResults",
}


@pytest.mark.parametrize("operation", [name for name in TOOLS if name != "status"])
def test_every_schema_parameter_reaches_the_wire(transport, operation: str) -> None:
    _, requests = transport
    schema = yaml.safe_load((ROOT / f"tools/mrscraper_{operation}.yaml").read_text())
    values = {parameter["name"]: _sample_value(parameter) for parameter in schema["parameters"]}

    _invoke(operation, values)

    query = _query(requests[0])
    for name, value in values.items():
        expected = str(value).lower() if isinstance(value, bool) else str(value)
        if operation == "scrape_html" and name == "browser_rendering":
            expected = "true"  # The sample screenshot forces browser rendering.
        assert query[WIRE_NAMES.get(name, name)] == expected, name


def test_binary_responses_become_blob_messages(transport) -> None:
    configure, _ = transport
    png = {"content-type": "image/png"}
    configure(lambda request: httpx.Response(200, content=b"\x89PNG", headers=png))

    messages = _invoke("get_screenshot", {"url": URL})

    assert messages[0].type.value == "blob"
    assert messages[0].message.blob == b"\x89PNG"


def test_client_can_run_inside_an_existing_event_loop(transport) -> None:
    async def invoke() -> Any:
        parameters = PARAMETERS["web_search"]({"query": "example"})
        return MrscraperClient(TOKEN).invoke("web_search", parameters)

    assert asyncio.run(invoke()) == {"items": ["result"]}


def test_unknown_operations_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        MrscraperClient(TOKEN).invoke("account", {})


def test_transport_errors_redact_the_token(transport) -> None:
    configure, _ = transport

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            f"Request failed: {request.url}; auth={request.headers['authorization']}",
            request=request,
        )

    configure(fail)
    with pytest.raises(MrscraperAPIError) as error:
        _invoke("scrape_html", {"url": URL})

    message = str(error.value)
    assert "[REDACTED]" in message
    for value in (TOKEN, quote(TOKEN, safe=""), quote_plus(TOKEN)):
        assert value not in message


@pytest.mark.parametrize("operation", list(TOOLS))
def test_http_error_bodies_are_redacted(transport, operation: str) -> None:
    configure, _ = transport
    configure(lambda request: httpx.Response(500, text=f"failed for {request.headers}"))
    parameters = {"query": "example"} if operation == "web_search" else {"url": URL}

    with pytest.raises(MrscraperAPIError) as error:
        _invoke(operation, {} if operation == "status" else parameters)

    assert "HTTP 500" in str(error.value)
    assert TOKEN not in str(error.value)
    assert quote_plus(TOKEN) not in str(error.value)


def test_provider_validates_with_status_and_reports_safe_auth_errors(transport) -> None:
    configure, requests = transport
    configure(lambda request: httpx.Response(200, json={"data": {"tokenLimit": 100}}))
    provider = MrscraperProvider()
    provider._validate_credentials({"api_token": TOKEN})
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v1/subscription-accounts"
    assert requests[0].extensions["timeout"]["read"] == 600

    configure(lambda request: httpx.Response(401, json={"error": TOKEN}))
    with pytest.raises(ToolProviderCredentialValidationError) as error:
        provider._validate_credentials({"api_token": TOKEN})
    assert "Unauthorized" in str(error.value)
    assert TOKEN not in str(error.value)
    with pytest.raises(ToolProviderCredentialValidationError, match="token is required"):
        provider._validate_credentials({})
    assert len(requests) == 2


PAGE_INVALID = [
    {"url": "file:///etc/hosts"},
    {"url": "example.com"},
    {"url": "http://[::1"},
    {"url": " "},
    {"timeout": 0},
    {"timeout": 331},
    {"timeout": 1.5},
    {"timeout": True},
    {"geo_code": "usa"},
    {"geo_code": 1},
    {"max_retries": -1},
    {"max_retries": 1.5},
    {"save_result": 1},
    {"save_result": "false"},
    {"max_age": -1},
    {"max_age": 604800001},
    {"max_age": 1.5},
    {"max_age": True},
    {"token_cap": 0},
    {"token_cap": 1.5},
    {"wait_for_selector": "a" * 501},
    {"wait_for_selector": 3},
]
LOADING_INVALID = [
    {"browser_rendering": "maybe"},
    {"browser_rendering": 1},
    {"warm_start": "yes"},
    {"block_resources": "false"},
]


@pytest.mark.parametrize("operation", ["scrape_html", "scrape_markdown", "scrape_json"])
@pytest.mark.parametrize("options", [*PAGE_INVALID, *LOADING_INVALID])
def test_invalid_loading_input_is_rejected_before_http(transport, operation, options) -> None:
    _, requests = transport

    with pytest.raises(ParameterValidationError):
        _invoke(operation, {"url": URL} | options)

    assert requests == []


@pytest.mark.parametrize("options", PAGE_INVALID)
def test_invalid_screenshot_input_is_rejected_before_http(transport, options) -> None:
    _, requests = transport

    with pytest.raises(ParameterValidationError):
        _invoke("get_screenshot", {"url": URL} | options)

    assert requests == []


@pytest.mark.parametrize(
    ("operation", "options"),
    [
        ("scrape_html", {"screenshot": True}),
        ("scrape_html", {"screenshot": "viewport"}),
        ("scrape_html", {"screenshot": "FULL"}),
        ("scrape_html", {"screenshot": "99x800"}),
        ("scrape_html", {"screenshot": "1280x3841"}),
        ("scrape_html", {"screenshot": "1280x800-24"}),
        ("scrape_html", {"screenshot": "1280x800-301"}),
        ("scrape_html", {"action": 3}),
        ("scrape_markdown", {"action": ["flow"]}),
        ("scrape_json", {"screenshot": "full"}),
        ("scrape_json", {"html": "true"}),
        ("scrape_json", {"prompt": "   "}),
        ("scrape_json", {"prompt": 1}),
        ("scrape_brand", {"url": "ftp://example.com"}),
        ("scrape_brand", {"url": None}),
    ],
)
def test_invalid_service_input_is_rejected_before_http(transport, operation, options) -> None:
    _, requests = transport

    with pytest.raises(ParameterValidationError):
        _invoke(operation, {"url": URL} | options)

    assert requests == []


@pytest.mark.parametrize(
    "options",
    [
        {"query": " "},
        {"query": None},
        {"query": "x" * 1001},
        {"num_results": 9},
        {"num_results": 101},
        {"num_results": 10.5},
        {"num_results": True},
        {"country": 1},
        {"country": "usa"},
    ],
)
def test_invalid_search_input_is_rejected_before_http(transport, options) -> None:
    _, requests = transport

    with pytest.raises(ParameterValidationError):
        _invoke("web_search", {"query": "example"} | options)

    assert requests == []


def test_query_of_exactly_one_thousand_characters_is_accepted(transport) -> None:
    _, requests = transport
    query = "é" * 1000

    _invoke("web_search", {"query": query})

    assert parse_qs(urlsplit(str(requests[0].url)).query)["query"] == [query]
