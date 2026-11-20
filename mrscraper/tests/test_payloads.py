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
PAGE_DEFAULT_QUERY = {
    "url": URL,
    "super": "false",
    "waitUntil": "domcontentloaded",
    "timeout": "300",
    "geoCode": "us",
    "proxyCountry": "us",
    "saveResult": "false",
}
LOADING_DEFAULT_QUERY = PAGE_DEFAULT_QUERY | {"blockResources": "false", "returnCookie": "false"}


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
    assert _query(request) == LOADING_DEFAULT_QUERY | {
        "browserRendering": "false",
        "warmStart": "false",
        "html": "true",
        "markdown": "false",
        "screenshot": "false",
    }
    _assert_authenticated(request, 330)


def test_scrape_html_sends_every_page_and_loading_control(transport) -> None:
    _, requests = transport

    _invoke(
        "scrape_html",
        {
            "url": URL,
            "timeout": 120.0,
            "geo_code": "ID",
            "proxy_country": "Sg",
            "super": True,
            "wait_until": "networkidle2",
            "proxy": "http://proxy.example.com:8080",
            "max_retries": 0,
            "save_result": True,
            "block_resources": True,
            "wait_for_selector": " body ",
            "return_cookie": True,
            "browser_rendering": True,
            "warm_start": True,
        },
    )

    request = requests[0]
    assert _query(request) == {
        "url": URL,
        "super": "true",
        "waitUntil": "networkidle2",
        "timeout": "120",
        "geoCode": "id",
        "proxyCountry": "sg",
        "saveResult": "true",
        "proxy": "http://proxy.example.com:8080",
        "maxRetries": "0",
        "waitForSelector": "body",
        "blockResources": "true",
        "returnCookie": "true",
        "browserRendering": "true",
        "warmStart": "true",
        "html": "true",
        "markdown": "false",
        "screenshot": "false",
    }
    _assert_authenticated(request, 150)


def test_scrape_markdown_with_html_enables_rendering_and_returns_json(transport) -> None:
    configure, requests = transport
    body = {"html": "<html>...</html>", "markdown": "# Example page"}
    configure(lambda request: httpx.Response(200, json=body))

    messages = _invoke("scrape_markdown", {"url": URL, "html": True, "warm_start": True})

    assert messages[0].type.value == "json"
    assert messages[0].message.json_object == body
    assert _query(requests[0]) == LOADING_DEFAULT_QUERY | {
        "browserRendering": "true",
        "warmStart": "true",
        "html": "true",
        "markdown": "true",
        "screenshot": "false",
    }


def test_scrape_markdown_defaults_return_markdown_text(transport) -> None:
    configure, requests = transport
    configure(
        lambda request: httpx.Response(
            200, text="# Example page", headers={"content-type": "text/markdown; charset=utf-8"}
        )
    )

    messages = _invoke("scrape_markdown", {"url": URL})

    assert messages[0].message.text == "# Example page"
    query = _query(requests[0])
    assert (query["browserRendering"], query["html"], query["markdown"]) == (
        "false",
        "false",
        "true",
    )
    assert query["warmStart"] == "false"


def test_get_screenshot_always_renders_and_defaults_to_full_page_with_html(transport) -> None:
    configure, requests = transport
    body = {"html": "<html>...</html>", "screenshot": "BASE64_PNG_DATA"}
    configure(lambda request: httpx.Response(200, json=body))

    messages = _invoke("get_screenshot", {"url": URL})

    assert messages[0].message.json_object == body
    request = requests[0]
    assert request.method == "GET"
    assert _query(request) == LOADING_DEFAULT_QUERY | {
        "browserRendering": "true",
        "warmStart": "false",
        "screenshot": "full",
        "html": "true",
        "markdown": "false",
    }
    _assert_authenticated(request, 330)


def test_get_screenshot_accepts_warm_start_top_viewport_and_markdown(transport) -> None:
    _, requests = transport

    _invoke(
        "get_screenshot",
        {"url": URL, "warm_start": True, "screenshot": "top", "html": False, "markdown": True},
    )

    query = _query(requests[0])
    assert query["warmStart"] == "true"
    assert query["screenshot"] == "top"
    assert (query["html"], query["markdown"], query["browserRendering"]) == (
        "false",
        "true",
        "true",
    )


def test_scrape_brand_requests_the_brand_action_only(transport) -> None:
    configure, requests = transport
    body = {"data": {"status": "succeeded", "brand": {"name": "Example brand"}}}
    configure(lambda request: httpx.Response(200, json=body))

    messages = _invoke("scrape_brand", {"url": URL, "timeout": 5, "warm_start": True})

    assert messages[0].message.json_object == body
    request = requests[0]
    assert request.method == "GET"
    assert _query(request) == {"action": "brand-scraping", "url": URL, "bundle": "none"}
    _assert_authenticated(request, 120)


def test_scrape_json_defaults_use_the_general_agent_and_default_prompt(transport) -> None:
    configure, requests = transport
    body = {"success": True, "data": [{"title": "Example item"}], "html": "", "screenshot": ""}
    configure(lambda request: httpx.Response(200, json=body))

    messages = _invoke("scrape_json", {"url": URL, "prompt": None})

    assert messages[0].message.json_object == body
    request = requests[0]
    assert request.method == "GET"
    assert request.content == b""
    assert _query(request) == PAGE_DEFAULT_QUERY | {
        "browserRendering": "false",
        "html": "false",
        "screenshot": "false",
        "agent": "general",
        "prompt": "Extract all data as complete as possible.",
    }
    _assert_authenticated(request, 330)


def test_scrape_json_ignores_loading_controls_and_sends_boolean_screenshot(transport) -> None:
    _, requests = transport

    _invoke(
        "scrape_json",
        {
            "url": URL,
            "prompt": 'Extract the title. Json Schema: {"type":"object"}',
            "browser_rendering": True,
            "html": True,
            "screenshot": True,
            "max_retries": 2,
            "block_resources": True,
            "wait_for_selector": "body",
            "return_cookie": True,
            "warm_start": True,
        },
    )

    query = _query(requests[0])
    assert query["prompt"] == 'Extract the title. Json Schema: {"type":"object"}'
    assert (query["browserRendering"], query["html"], query["screenshot"]) == ("true",) * 3
    assert query["maxRetries"] == "2"
    for name in ("blockResources", "waitForSelector", "returnCookie", "warmStart", "markdown"):
        assert name not in query


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
    assert _query(request) == {
        "action": "websearch",
        "query": "site:example.com documentation",
        "country": "id",
        "numResults": "20",
    }
    _assert_authenticated(request, 120)


def test_web_search_defaults_to_us_and_ten_results(transport) -> None:
    _, requests = transport

    _invoke("web_search", {"query": "example domain", "country": " ", "num_results": None})

    assert _query(requests[0]) == {
        "action": "websearch",
        "query": "example domain",
        "country": "us",
        "numResults": "10",
    }


def _sample_value(parameter: dict) -> Any:
    name = parameter["name"]
    if parameter["type"] == "boolean":
        return not parameter.get("default", False)
    if parameter["type"] == "select":
        return parameter["options"][-1]["value"]
    if parameter["type"] == "number":
        return {"timeout": 45, "max_retries": 4, "num_results": 30}[name]
    return {
        "url": "https://example.com/changed",
        "geo_code": "de",
        "proxy_country": "fr",
        "proxy": "http://proxy.example.com:3128",
        "wait_for_selector": "main",
        "prompt": "Extract the heading.",
        "query": "changed query",
        "country": "gb",
    }[name]


WIRE_NAMES = {
    "geo_code": "geoCode",
    "proxy_country": "proxyCountry",
    "wait_until": "waitUntil",
    "max_retries": "maxRetries",
    "save_result": "saveResult",
    "block_resources": "blockResources",
    "wait_for_selector": "waitForSelector",
    "return_cookie": "returnCookie",
    "browser_rendering": "browserRendering",
    "warm_start": "warmStart",
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
        if operation == "scrape_markdown" and name == "browser_rendering":
            expected = "true"
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


def test_transport_errors_redact_the_token_and_proxy(transport) -> None:
    configure, _ = transport
    proxy = "http://placeholder-user:placeholder+secret@proxy.example.com:8080"

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            f"Request failed: {request.url}; auth={request.headers['authorization']}",
            request=request,
        )

    configure(fail)
    with pytest.raises(MrscraperAPIError) as error:
        _invoke("scrape_html", {"url": URL, "proxy": proxy})

    message = str(error.value)
    assert "[REDACTED]" in message
    for secret in (TOKEN, proxy):
        for value in (secret, quote(secret, safe=""), quote_plus(secret)):
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
    {"timeout": 301},
    {"timeout": 1.5},
    {"timeout": True},
    {"geo_code": "usa"},
    {"proxy_country": "1a"},
    {"super": "true"},
    {"wait_until": "networkidle"},
    {"max_retries": -1},
    {"max_retries": 1.5},
    {"save_result": 1},
    {"proxy": 42},
]


@pytest.mark.parametrize("operation", ["scrape_html", "scrape_markdown", "get_screenshot"])
@pytest.mark.parametrize(
    "options",
    [
        *PAGE_INVALID,
        {"block_resources": "false"},
        {"return_cookie": None, "wait_for_selector": 3},
        {"warm_start": "yes"},
    ],
)
def test_invalid_page_input_is_rejected_before_http(transport, operation, options) -> None:
    _, requests = transport

    with pytest.raises(ParameterValidationError):
        _invoke(operation, {"url": URL} | options)

    assert requests == []


@pytest.mark.parametrize(
    ("operation", "options"),
    [
        ("scrape_html", {"browser_rendering": "auto"}),
        ("scrape_markdown", {"html": "true"}),
        ("get_screenshot", {"screenshot": True}),
        ("get_screenshot", {"screenshot": "viewport"}),
        ("get_screenshot", {"markdown": "false"}),
        ("scrape_json", {"screenshot": "full"}),
        ("scrape_json", {"prompt": "   "}),
        ("scrape_json", {"prompt": 1}),
        *[("scrape_json", options) for options in PAGE_INVALID],
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
