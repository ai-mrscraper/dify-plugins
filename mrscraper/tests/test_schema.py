from pathlib import Path

import pytest
import yaml
from dify_plugin import Tool
from dify_plugin.core.utils.class_loader import load_single_subclass_from_source
from dify_plugin.entities.tool import ToolParameter

ROOT = Path(__file__).parents[1]

# The standard service reference: tool description, then parameters in order.
SERVICE_DESCRIPTIONS = {
    "status": "Return the raw account status API response without summarizing, redacting body "
    "fields, or adding calculated fields.",
    "scrape_html": "Retrieve the raw HTML of a page. Browser rendering is optional.",
    "scrape_markdown": "Retrieve a page as Markdown. Including HTML also enables browser rendering "
    "and returns both outputs as JSON.",
    "get_screenshot": "Capture a base64 screenshot of the full page or top viewport. Browser "
    "rendering is always enabled.",
    "scrape_brand": "Extract a website's colors, typography, logos, and social links as JSON.",
    "scrape_json": "Extract structured JSON from a page using a natural-language prompt. Append "
    "Json Schema: and a JSON schema to shape the output.",
    "web_search": "Search the web and return ranked results with titles, URLs, descriptions, "
    "and sources.",
}
PARAMETER_DESCRIPTIONS = {
    "url": "Absolute HTTP or HTTPS URL of the page to process.",
    "timeout": "Page load timeout in seconds, from 1 to 300. The HTTP request allows 30 "
    "additional seconds.",
    "geo_code": "Two-letter country code to load the page from, sent in lowercase.",
    "proxy_country": "Two-letter country code of the proxy server, sent in lowercase.",
    "super": "Whether to route the request through real devices.",
    "wait_until": "Navigation completion event to wait for: domcontentloaded, load, networkidle0, "
    "or networkidle2.",
    "proxy": "Custom proxy URL used to load the page.",
    "max_retries": "Maximum number of retries, as a nonnegative integer. Omit this parameter for "
    "no limit.",
    "save_result": "Whether to save the result to the dashboard Result tab.",
    "block_resources": "Whether to block images, fonts, and stylesheets while loading the page.",
    "wait_for_selector": "Wait for the page to contain the specified CSS selector before "
    "returning the result.",
    "return_cookie": "Whether to include browser session cookies in the response.",
    "browser_rendering": "Whether to render the page in a browser before returning the result.",
    "warm_start": "Whether to enable warm start for more reliable scraping, at the cost of "
    "additional latency.",
    "html": "Whether to include the page HTML in the response.",
    "markdown": "Whether to include the page Markdown in the response.",
    "prompt": "Instructions describing the data to extract. Append Json Schema: and a JSON schema "
    "to shape the output.",
    "query": "Search query text, trimmed before sending, containing 1 to 1000 characters.",
    "country": "Two-letter country code to search from, sent in lowercase.",
    "num_results": "Number of search results to request, as an integer from 10 to 100. Fewer "
    "results may be returned.",
}
SCREENSHOT_DESCRIPTIONS = {
    "get_screenshot": "Screenshot area to capture: full for the entire page or top for the top "
    "viewport.",
    "scrape_json": "Whether to include a base64 screenshot in the response.",
}
PAGE = [
    "url",
    "timeout",
    "geo_code",
    "proxy_country",
    "super",
    "wait_until",
    "proxy",
    "max_retries",
    "save_result",
]
LOADING = ["block_resources", "wait_for_selector", "return_cookie"]
SERVICE_PARAMETERS = {
    "status": [],
    "scrape_html": [*PAGE, *LOADING, "browser_rendering", "warm_start"],
    "scrape_markdown": [*PAGE, *LOADING, "browser_rendering", "warm_start", "html"],
    # Get screenshot adds warm_start to the standard reference.
    "get_screenshot": [*PAGE, *LOADING, "warm_start", "screenshot", "html", "markdown"],
    "scrape_brand": ["url"],
    "scrape_json": [*PAGE, "prompt", "browser_rendering", "html", "screenshot"],
    "web_search": ["query", "country", "num_results"],
}
DEFAULTS = {
    "timeout": 300,
    "geo_code": "us",
    "proxy_country": "us",
    "super": False,
    "wait_until": "domcontentloaded",
    "save_result": False,
    "block_resources": False,
    "return_cookie": False,
    "browser_rendering": False,
    "warm_start": False,
    "html": False,
    "markdown": False,
    "prompt": "Extract all data as complete as possible.",
    "country": "us",
    "num_results": 10,
}
CLASS_NAMES = {
    "status": "MrscraperStatusTool",
    "scrape_html": "MrscraperScrapeHtmlTool",
    "scrape_markdown": "MrscraperScrapeMarkdownTool",
    "get_screenshot": "MrscraperGetScreenshotTool",
    "scrape_brand": "MrscraperScrapeBrandTool",
    "scrape_json": "MrscraperScrapeJsonTool",
    "web_search": "MrscraperWebSearchTool",
}


def _schema(operation: str) -> dict:
    return yaml.safe_load((ROOT / f"tools/mrscraper_{operation}.yaml").read_text())


def test_provider_registers_exactly_the_seven_services_in_order() -> None:
    provider = yaml.safe_load((ROOT / "provider/mrscraper.yaml").read_text())

    assert provider["tools"] == [f"tools/mrscraper_{name}.yaml" for name in SERVICE_DESCRIPTIONS]
    assert {path.stem for path in (ROOT / "tools").glob("*.yaml")} == {
        f"mrscraper_{name}" for name in SERVICE_DESCRIPTIONS
    }
    assert {path.stem for path in (ROOT / "tools").glob("*.py")} == {
        f"mrscraper_{name}" for name in SERVICE_DESCRIPTIONS
    }


@pytest.mark.parametrize("operation", list(SERVICE_DESCRIPTIONS))
def test_tool_schema_matches_the_standard_reference(operation: str) -> None:
    schema = _schema(operation)
    name = f"mrscraper_{operation}"

    assert schema["identity"]["name"] == name
    assert schema["extra"]["python"]["source"] == f"tools/{name}.py"
    assert schema["description"]["llm"] == SERVICE_DESCRIPTIONS[operation]
    assert schema["description"]["human"]["en_US"] == SERVICE_DESCRIPTIONS[operation]
    parameters = schema["parameters"]
    assert [parameter["name"] for parameter in parameters] == SERVICE_PARAMETERS[operation]
    for parameter in parameters:
        ToolParameter.model_validate(parameter)
        expected = (
            SCREENSHOT_DESCRIPTIONS[operation]
            if parameter["name"] == "screenshot"
            else PARAMETER_DESCRIPTIONS[parameter["name"]]
        )
        assert parameter["llm_description"] == expected
        assert parameter["human_description"]["en_US"] == expected
        assert parameter["form"] == "llm"
        assert parameter["required"] is (parameter["name"] in {"url", "query"})


@pytest.mark.parametrize("operation", list(SERVICE_DESCRIPTIONS))
def test_schema_defaults_and_types_follow_the_reference(operation: str) -> None:
    parameters = {parameter["name"]: parameter for parameter in _schema(operation)["parameters"]}

    for name, parameter in parameters.items():
        if name in {"url", "query", "proxy", "max_retries", "wait_for_selector"}:
            assert "default" not in parameter, name
        elif name == "screenshot" or (operation == "get_screenshot" and name == "html"):
            continue
        else:
            assert parameter["default"] == DEFAULTS[name], name
        if isinstance(DEFAULTS.get(name), bool):
            assert parameter["type"] == "boolean"
    if "wait_until" in parameters:
        wait_until = parameters["wait_until"]
        assert wait_until["type"] == "select"
        assert [option["value"] for option in wait_until["options"]] == [
            "domcontentloaded",
            "load",
            "networkidle0",
            "networkidle2",
        ]
    for name, bounds in {"timeout": (1, 300), "num_results": (10, 100)}.items():
        if name in parameters:
            parameter = parameters[name]
            assert (parameter["type"], parameter["min"], parameter["max"]) == ("number", *bounds)
            assert parameter["precision"] == 0
    if "max_retries" in parameters:
        assert (parameters["max_retries"]["min"], parameters["max_retries"]["precision"]) == (0, 0)
        assert "max" not in parameters["max_retries"]


def test_screenshot_parameter_forms_differ_by_service() -> None:
    capture = {p["name"]: p for p in _schema("get_screenshot")["parameters"]}
    extraction = {p["name"]: p for p in _schema("scrape_json")["parameters"]}

    assert capture["screenshot"]["type"] == "select"
    assert capture["screenshot"]["default"] == "full"
    assert [option["value"] for option in capture["screenshot"]["options"]] == ["full", "top"]
    assert capture["html"]["default"] is True
    assert capture["warm_start"]["default"] is False
    assert extraction["screenshot"]["type"] == "boolean"
    assert extraction["screenshot"]["default"] is False


@pytest.mark.parametrize("operation", list(SERVICE_DESCRIPTIONS))
def test_each_registered_source_loads_a_single_tool_subclass(operation: str) -> None:
    tool_class = load_single_subclass_from_source(
        module_name=f"test_mrscraper_{operation}",
        script_path=str(ROOT / f"tools/mrscraper_{operation}.py"),
        parent_type=Tool,
    )
    assert tool_class.__name__ == CLASS_NAMES[operation]


def test_manifest_and_project_versions_match_and_network_domains_are_minimal() -> None:
    manifest = yaml.safe_load((ROOT / "manifest.yaml").read_text())
    pyproject = (ROOT / "pyproject.toml").read_text()

    assert manifest["version"] == "0.3.0"
    assert f'version = "{manifest["version"]}"' in pyproject
    assert manifest["network"]["domains"] == ["api.app.mrscraper.com", "api.mrscraper.com"]
    assert "feat/mrscraper-0.3.0-source" in manifest["repo"]
