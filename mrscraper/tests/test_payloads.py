import asyncio
import json
from collections.abc import Callable
from typing import Any
from urllib.parse import quote, quote_plus

import httpx
import pytest
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from mrscraper import MrScraper

import common.client
from common.client import MrscraperAPIError, MrscraperClient
from common.parameters import account_parameters, scraper_parameters, search_parameters
from common.validation import ParameterValidationError
from provider.mrscraper import MrscraperProvider
from tools.mrscraper_account import MrscraperAccountTool
from tools.mrscraper_scraper_api import MrscraperScraperApiTool
from tools.mrscraper_web_search import MrscraperWebSearchTool

TOKEN = "test-api-token+secret"


@pytest.fixture
def sdk_transport(monkeypatch: pytest.MonkeyPatch):
    """Run the installed SDK against an in-memory HTTP endpoint."""
    requests: list[httpx.Request] = []
    clients: list[httpx.AsyncClient] = []

    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": ["result"]})

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return responder(request)

    def factory(*, token: str) -> MrScraper:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        clients.append(client)
        return MrScraper(token=token, http_client=client)

    def configure(handler: Callable[[httpx.Request], httpx.Response]) -> list[httpx.Request]:
        nonlocal responder
        responder = handler
        return requests

    monkeypatch.setattr(common.client, "MrScraper", factory)
    yield configure, requests
    for client in clients:
        asyncio.run(client.aclose())


def test_scraper_uses_sdk_defaults_and_emits_inner_html(sdk_transport) -> None:
    configure, requests = sdk_transport
    configure(lambda request: httpx.Response(200, text="<html>Example</html>"))
    tool = MrscraperScraperApiTool.from_credentials({"api_token": TOKEN})

    messages = list(tool._invoke({"url": " https://example.com/page "}))

    assert len(messages) == 1
    assert messages[0].type.value == "text"
    assert messages[0].message.text == "<html>Example</html>"
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url.copy_with(query=None)) == "https://api.mrscraper.com"
    assert dict(request.url.params) == {
        "token": TOKEN,
        "timeout": "120",
        "geoCode": "US",
        "html": "true",
        "markdown": "false",
    }
    assert json.loads(request.content) == {"url": "https://example.com/page", "maxRetries": 3}
    assert request.extensions["timeout"]["read"] == 150


def test_scraper_preserves_explicit_false_and_zero_at_sdk_boundary(sdk_transport) -> None:
    _, requests = sdk_transport
    parameters = scraper_parameters(
        {
            "url": "https://example.com",
            "html": False,
            "markdown": False,
            "browser_rendering": "false",
            "stream": "false",
            "use_proxy": False,
            "max_retries": 0,
            "token_cap": 0,
            "headers": '{"Accept-Language":"id-ID"}',
            "timeout": 300,
        }
    )

    assert MrscraperClient(TOKEN).invoke("scraper_api", parameters) == {"items": ["result"]}

    request = requests[0]
    query = dict(request.url.params)
    names = ("html", "markdown", "browserRendering", "stream", "useProxy")
    assert {name: query[name] for name in names} == dict.fromkeys(names, "false")
    assert json.loads(query["headers"]) == {"Accept-Language": "id-ID"}
    assert json.loads(request.content) == {
        "url": "https://example.com",
        "maxRetries": 0,
        "tokenCap": 0,
    }
    assert request.extensions["timeout"]["read"] == 330


def test_screenshot_forces_rendering_and_home_page_uses_warm_start(sdk_transport) -> None:
    _, requests = sdk_transport
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
            }
        ),
    )

    query = requests[0].url.params
    assert query["screenshot"] == query["browserRendering"] == "true"
    assert query["warmStart"] == query["super"] == "true"
    assert "homePage" not in query
    assert "stream" not in query


def test_search_parses_google_url_and_explicit_options_override_it(sdk_transport) -> None:
    _, requests = sdk_transport
    tool = MrscraperWebSearchTool.from_credentials({"api_token": TOKEN})
    parameters = {
        "url": "https://www.google.com/search?q=python+scraping&gl=us&hl=en&start=20",
        "raw": False,
    }

    messages = list(tool._invoke(parameters))
    list(
        tool._invoke(
            parameters
            | {
                "region": "id",
                "language": "id",
                "page": 2,
                "render_js": True,
                "timeout": 45.5,
            }
        )
    )

    assert messages[0].type.value == "json"
    assert messages[0].message.json_object == {"items": ["result"]}
    request = requests[0]
    assert str(request.url) == "https://sync.scraper.mrscraper.com/api/google/serp/v2/sync"
    assert json.loads(request.content) == {
        "query": "python scraping",
        "region": "us",
        "language": "en",
        "page": 3,
        "format": "json",
        "renderJs": False,
    }
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert request.headers["x-api-token"] == TOKEN
    assert request.extensions["timeout"]["read"] == 600
    assert json.loads(requests[1].content) == {
        "query": "python scraping",
        "region": "id",
        "language": "id",
        "page": 2,
        "format": "json",
        "renderJs": True,
    }
    assert requests[1].extensions["timeout"]["read"] == 45.5


def test_search_retains_sdk_raw_html_default(sdk_transport) -> None:
    configure, requests = sdk_transport
    configure(lambda request: httpx.Response(200, text="<html>Search</html>"))

    messages = list(
        MrscraperWebSearchTool.from_credentials({"api_token": TOKEN})._invoke(
            {"url": "python scraping", "format": "json"}
        )
    )

    assert json.loads(requests[0].content) == {
        "query": "python scraping",
        "format": "html",
        "renderJs": False,
    }
    assert messages[0].message.text == "<html>Search</html>"


def test_account_uses_sdk_safe_summary_and_never_emits_credentials(sdk_transport) -> None:
    configure, requests = sdk_transport
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
    assert request.extensions["timeout"]["read"] == 30


def test_sync_client_can_run_inside_an_existing_event_loop(sdk_transport) -> None:
    async def invoke() -> Any:
        return MrscraperClient(TOKEN).invoke("web_search", search_parameters({"url": "example"}))

    assert asyncio.run(invoke()) == {"items": ["result"]}


def test_transport_errors_redact_encoded_credentials(sdk_transport) -> None:
    configure, _ = sdk_transport
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


def test_provider_validates_with_account_and_reports_safe_auth_errors(sdk_transport) -> None:
    configure, requests = sdk_transport
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
    ],
)
def test_invalid_scraper_input_is_rejected_before_http(sdk_transport, options) -> None:
    _, requests = sdk_transport
    tool = MrscraperScraperApiTool.from_credentials({"api_token": TOKEN})

    with pytest.raises(ParameterValidationError):
        list(tool._invoke({"url": "https://example.com"} | options))

    assert requests == []


@pytest.mark.parametrize(
    "options",
    [
        {"url": " "},
        {"page": 0},
        {"page": 1.5},
        {"format": "xml"},
        {"timeout": 0},
        {"timeout": float("inf")},
        {"timeout": float("nan")},
    ],
)
def test_invalid_search_input_is_rejected_before_http(sdk_transport, options) -> None:
    _, requests = sdk_transport
    tool = MrscraperWebSearchTool.from_credentials({"api_token": TOKEN})

    with pytest.raises(ParameterValidationError):
        list(tool._invoke({"url": "example"} | options))

    assert requests == []


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_account_rejects_invalid_deadlines(timeout) -> None:
    with pytest.raises(ParameterValidationError):
        account_parameters({"timeout": timeout})
