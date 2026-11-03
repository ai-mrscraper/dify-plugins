import asyncio
import json
from collections.abc import Callable
from typing import Any
from urllib.parse import quote, quote_plus

import httpx
import pytest
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from common.client import MrscraperAPIError, MrscraperClient
from common.parameters import account_parameters, scraper_parameters, search_parameters
from common.validation import ParameterValidationError
from provider.mrscraper import MrscraperProvider
from tools.mrscraper_account import MrscraperAccountTool
from tools.mrscraper_scraper_api import MrscraperScraperApiTool
from tools.mrscraper_web_search import MrscraperWebSearchTool

TOKEN = "test-api-token+secret"
SEARCH_RESPONSE = {
    "success": True,
    "message": "Search completed",
    "data": [
        {
            "rank": 1,
            "title": "Example",
            "url": "https://example.com",
            "description": "Example result",
            "source": "example.com",
        }
    ],
}


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


def test_scraper_sends_everything_in_a_get_query_and_emits_html_text(transport) -> None:
    configure, requests = transport
    configure(
        lambda request: httpx.Response(
            200, text="<html>Example</html>", headers={"content-type": "text/html"}
        )
    )
    tool = MrscraperScraperApiTool.from_credentials({"api_token": TOKEN})

    messages = list(tool._invoke({"url": " https://example.com/page "}))

    assert len(messages) == 1
    assert messages[0].type.value == "text"
    assert messages[0].message.text == "<html>Example</html>"
    request = requests[0]
    assert request.method == "GET"
    assert request.content == b""
    assert str(request.url.copy_with(query=None)) == "https://api.mrscraper.com"
    assert dict(request.url.params) == {
        "token": TOKEN,
        "url": "https://example.com/page",
        "html": "true",
        "markdown": "false",
        "timeout": "120",
        "geoCode": "US",
        "maxRetries": "3",
    }
    assert request.headers["x-api-token"] == TOKEN
    assert "authorization" not in request.headers
    assert request.extensions["timeout"]["read"] == 150


def test_scraper_combination_returns_json_object(transport) -> None:
    configure, requests = transport
    body = {"html": "<html></html>", "markdown": "# Example", "screenshot": "aGVsbG8="}
    configure(lambda request: httpx.Response(200, json=body))
    tool = MrscraperScraperApiTool.from_credentials({"api_token": TOKEN})

    messages = list(
        tool._invoke(
            {"url": "https://example.com", "html": True, "markdown": True, "screenshot": True}
        )
    )

    assert messages[0].type.value == "json"
    assert messages[0].message.json_object == body
    query = requests[0].url.params
    assert query["html"] == query["markdown"] == query["screenshot"] == "true"
    assert query["browserRendering"] == "true"


def test_scraper_preserves_explicit_false_and_zero_in_query(transport) -> None:
    _, requests = transport
    parameters = scraper_parameters(
        {
            "url": "https://example.com",
            "html": False,
            "markdown": True,
            "browser_rendering": "false",
            "stream": "false",
            "use_proxy": False,
            "max_retries": 0,
            "token_cap": 0,
            "headers": '{"Accept-Language":"id-ID"}',
            "timeout": 300,
            "wait_until": "domcontentloaded",
        }
    )

    assert MrscraperClient(TOKEN).invoke("scraper_api", parameters) == {"items": ["result"]}

    request = requests[0]
    query = dict(request.url.params)
    names = ("html", "browserRendering", "stream", "useProxy")
    assert {name: query[name] for name in names} == dict.fromkeys(names, "false")
    assert query["markdown"] == "true"
    assert query["maxRetries"] == query["tokenCap"] == "0"
    assert query["waitUntil"] == "domcontentloaded"
    assert json.loads(query["headers"]) == {"Accept-Language": "id-ID"}
    assert request.content == b""
    assert request.extensions["timeout"]["read"] == 330


def test_screenshot_forces_rendering_and_home_page_uses_warm_start(transport) -> None:
    _, requests = transport
    MrscraperClient(TOKEN).invoke(
        "scraper_api",
        scraper_parameters(
            {
                "url": "https://example.com",
                "browser_rendering": "false",
                "stream": "auto",
                "screenshot": True,
                "home_page": True,
                "super": True,
                "discard_token_secret": "discard",
            }
        ),
    )

    request = requests[0]
    query = request.url.params
    assert query["screenshot"] == query["browserRendering"] == "true"
    assert query["warmStart"] == query["super"] == "true"
    assert "homePage" not in query
    assert "stream" not in query
    assert request.headers["x-discard-token-secret"] == "discard"


def test_web_search_posts_websearch_action(transport) -> None:
    configure, requests = transport
    configure(lambda request: httpx.Response(200, json=SEARCH_RESPONSE))
    tool = MrscraperWebSearchTool.from_credentials({"api_token": TOKEN})

    messages = list(
        tool._invoke({"query": " e-menessaptieka.lv linkedin ", "country": "us", "num_results": 25})
    )

    assert messages[0].type.value == "json"
    assert messages[0].message.json_object == SEARCH_RESPONSE
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.mrscraper.com"
    assert request.headers["x-api-token"] == TOKEN
    assert request.headers["content-type"] == "application/json"
    assert json.loads(request.content) == {
        "action": "websearch",
        "query": "e-menessaptieka.lv linkedin",
        "country": "us",
        "numResults": 25,
    }
    assert request.extensions["timeout"]["read"] == 600


def test_web_search_defaults_omit_country_and_request_ten_results(transport) -> None:
    _, requests = transport
    tool = MrscraperWebSearchTool.from_credentials({"api_token": TOKEN})

    list(tool._invoke({"query": "python web scraping", "country": " ", "num_results": None}))

    assert json.loads(requests[0].content) == {
        "action": "websearch",
        "query": "python web scraping",
        "numResults": 10,
    }


def test_web_search_reports_api_validation_errors(transport) -> None:
    configure, _ = transport
    configure(
        lambda request: httpx.Response(
            400, json={"success": False, "message": "Number must be greater than or equal to 10"}
        )
    )

    with pytest.raises(MrscraperAPIError, match="HTTP 400.*greater than or equal to 10"):
        MrscraperClient(TOKEN).invoke("web_search", {"query": "x", "num_results": 5})


def test_account_returns_safe_summary_and_never_emits_credentials(transport) -> None:
    configure, requests = transport
    configure(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "stripeStatus": "active",
                    "tokenUsage": "125",
                    "tokenLimit": "100",
                    "rateLimit": "5",
                    "rateTtl": 60,
                    "isEnterprise": True,
                    "isAutoRenew": True,
                    "endsAt": "2026-11-01",
                    "apiToken": "account-api-secret",
                    "stripeCustomerId": "billing-secret",
                    "user": {
                        "name": "Example",
                        "email": "example@example.com",
                        "isVerified": True,
                        "apiToken": "user-api-secret",
                    },
                }
            },
            headers={"set-cookie": "session=response-secret", "x-api-token": "response-api-secret"},
        )
    )

    messages = list(MrscraperAccountTool.from_credentials({"api_token": TOKEN})._invoke({}))

    assert len(messages) == 1
    data = messages[0].message.json_object
    assert data == {
        "subscription_status": "active",
        "enterprise": True,
        "token_usage": 125,
        "token_limit": 100,
        "token_remaining": 0,
        "usage_percent": 125,
        "rate_limit": 5,
        "rate_ttl": 60,
        "auto_renew": True,
        "ends_at": "2026-11-01",
        "user": {"name": "Example", "email": "example@example.com", "verified": True},
    }
    serialized = messages[0].model_dump_json()
    assert "secret" not in serialized
    assert "headers" not in serialized
    request = requests[0]
    assert request.method == "GET"
    assert str(request.url) == "https://api.app.mrscraper.com/api/v1/subscription-accounts"
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert request.headers["x-api-token"] == TOKEN
    assert request.extensions["timeout"]["read"] == 30


def test_binary_responses_become_blob_messages(transport) -> None:
    configure, _ = transport
    configure(
        lambda request: httpx.Response(
            200, content=b"\x89PNG", headers={"content-type": "image/png"}
        )
    )
    tool = MrscraperScraperApiTool.from_credentials({"api_token": TOKEN})

    messages = list(tool._invoke({"url": "https://example.com", "screenshot": True}))

    assert messages[0].type.value == "blob"
    assert messages[0].message.blob == b"\x89PNG"


def test_client_can_run_inside_an_existing_event_loop(transport) -> None:
    async def invoke() -> Any:
        return MrscraperClient(TOKEN).invoke("web_search", search_parameters({"query": "example"}))

    assert asyncio.run(invoke()) == {"items": ["result"]}


def test_transport_errors_redact_encoded_credentials(transport) -> None:
    configure, _ = transport
    secrets = (
        TOKEN,
        "user:p+ass@proxy.example:8080",
        "session=cookie+secret",
        "discard/secret",
        'Bearer target+header-"secret"',
    )

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            f"Request failed: {request.url}; discard={request.headers['x-discard-token-secret']}",
            request=request,
        )

    configure(fail)
    with pytest.raises(MrscraperAPIError) as error:
        MrscraperClient(TOKEN).invoke(
            "scraper_api",
            {
                "url": "https://example.com",
                "proxy": secrets[1],
                "cookie_jar": secrets[2],
                "discard_token_secret": secrets[3],
                "headers": {"Authorization": secrets[4]},
            },
        )

    message = str(error.value)
    assert "[REDACTED]" in message
    for secret in secrets:
        assert all(
            value not in message
            for value in (
                secret,
                quote(secret, safe=""),
                quote_plus(secret),
            )
        )


def test_http_error_bodies_are_redacted(transport) -> None:
    configure, _ = transport
    configure(lambda request: httpx.Response(500, text=f"failed for {request.url}"))

    with pytest.raises(MrscraperAPIError) as error:
        MrscraperClient(TOKEN).invoke("scraper_api", {"url": "https://example.com"})

    assert "HTTP 500" in str(error.value)
    assert TOKEN not in str(error.value)
    assert quote_plus(TOKEN) not in str(error.value)


def test_provider_validates_with_account_and_reports_safe_auth_errors(transport) -> None:
    configure, requests = transport
    configure(lambda request: httpx.Response(200, json={"tokenLimit": 100, "tokenUsage": 1}))
    provider = MrscraperProvider()
    provider._validate_credentials({"api_token": TOKEN})
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v1/subscription-accounts"
    assert requests[0].extensions["timeout"]["read"] == 30

    configure(lambda request: httpx.Response(401, json={"error": TOKEN}))
    with pytest.raises(ToolProviderCredentialValidationError) as error:
        provider._validate_credentials({"api_token": TOKEN})
    assert "Unauthorized" in str(error.value)
    assert TOKEN not in str(error.value)
    with pytest.raises(ToolProviderCredentialValidationError, match="token is required"):
        provider._validate_credentials({})
    assert len(requests) == 2


@pytest.mark.parametrize(
    "options",
    [
        {"url": "file:///etc/hosts"},
        {"url": "example.com"},
        {"timeout": 0},
        {"timeout": 301},
        {"timeout": 1.5},
        {"max_retries": -1},
        {"token_cap": -1},
        {"screenshot": "false"},
        {"headers": "[]"},
        {"headers": '{"Authorization":42}'},
        {"browser_rendering": "maybe"},
        {"html": False},
        {"html": False, "markdown": False, "screenshot": False},
    ],
)
def test_invalid_scraper_input_is_rejected_before_http(transport, options) -> None:
    _, requests = transport
    tool = MrscraperScraperApiTool.from_credentials({"api_token": TOKEN})

    with pytest.raises(ParameterValidationError):
        list(tool._invoke({"url": "https://example.com"} | options))

    assert requests == []


@pytest.mark.parametrize(
    "options",
    [
        {"query": " "},
        {"query": None},
        {"num_results": 9},
        {"num_results": 101},
        {"num_results": 10.5},
        {"num_results": True},
        {"country": 1},
    ],
)
def test_invalid_search_input_is_rejected_before_http(transport, options) -> None:
    _, requests = transport
    tool = MrscraperWebSearchTool.from_credentials({"api_token": TOKEN})

    with pytest.raises(ParameterValidationError):
        list(tool._invoke({"query": "example"} | options))

    assert requests == []


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_account_rejects_invalid_deadlines(timeout) -> None:
    with pytest.raises(ParameterValidationError):
        account_parameters({"timeout": timeout})
