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
    "scrape_markdown": "Retrieve a page as clean Markdown. Browser rendering is optional.",
    "get_screenshot": "Capture a base64 PNG screenshot of the full page, the first viewport, or a "
    "custom viewport. Browser rendering is always enabled.",
    "scrape_brand": "Extract a website's colors, typography, logos, and social links as JSON.",
    "scrape_json": "Extract structured JSON from a page using a natural-language prompt. Append "
    "Json Schema: and a JSON schema to shape the output.",
    "web_search": "Search the web and return ranked results with titles, URLs, descriptions, "
    "and sources.",
}
PARAMETER_DESCRIPTIONS = {
    "url": "Absolute HTTP or HTTPS URL of the page to process.",
    "prompt": "Instructions describing the data to extract. Append Json Schema: and a JSON schema "
    "to shape the output.",
    "html": "Whether to include the page HTML in the response.",
    "browser_rendering": "Whether to load the page in a browser: true always does and false never "
    "does. Omit it to load the page without a browser first and switch to a browser automatically "
    "if the request is blocked.",
    "timeout": "Maximum seconds to wait for the scrape, from 1 to 330. The HTTP request allows 30 "
    "additional seconds.",
    "warm_start": "Whether to open the site's home page first to warm the session before loading "
    "the target URL.",
    "block_resources": "Whether to block images, fonts, and stylesheets while loading the page.",
    "wait_for_selector": "CSS selector or text to wait for on the page before returning the "
    "result, up to 500 characters.",
    "geo_code": "Two-letter country code to load the page from, sent in lowercase.",
    "max_age": "Return a cached result of the same request when it is newer than the selected "
    "age. A cached result costs the same tokens as the original scrape.",
    "max_retries": "Maximum number of retries, as a nonnegative integer. Omit this parameter for "
    "no limit.",
    "query": "Search query text, trimmed before sending, containing 1 to 1000 characters.",
    "country": "Two-letter country code to search from, sent in lowercase.",
    "num_results": "Number of search results to request, as an integer from 10 to 100. Fewer "
    "results may be returned.",
}
SCREENSHOT_DESCRIPTIONS = {
    "get_screenshot": "Screenshot area to capture: full for the entire scroll height, top for the "
    "first viewport, or a WIDTHxHEIGHT viewport from 100 to 3840 pixels with an optional -ZOOM "
    "percent from 25 to 300, such as 1280x800 or 1920x1080-75.",
    "scrape_html": "Screenshot to capture with the HTML: false for none, full for the entire page, "
    "top for the first viewport, or a WIDTHxHEIGHT viewport from 100 to 3840 pixels with an "
    "optional -ZOOM percent from 25 to 300, such as 1280x800 or 1920x1080-75. Setting a "
    "screenshot also sends browserRendering=true.",
    "scrape_json": "Whether to include a base64 screenshot in the response.",
}
LOADING = ["browser_rendering", "timeout", "warm_start", "block_resources", "wait_for_selector"]
CACHE = ["geo_code", "max_age", "max_retries"]
SERVICE_PARAMETERS = {
    "status": [],
    "scrape_html": ["url", *LOADING, *CACHE, "screenshot"],
    "scrape_markdown": ["url", *LOADING, *CACHE],
    "get_screenshot": ["url", "screenshot", "timeout", "wait_for_selector", *CACHE],
    "scrape_brand": ["url"],
    "scrape_json": ["url", "prompt", "html", *LOADING, *CACHE, "screenshot"],
    "web_search": ["query", "country", "num_results"],
}
# Inputs without a default are omitted from the request unless set.
OMITTED = {"url", "query", "wait_for_selector", "geo_code", "max_retries", "country"}
OMITTED_BY_SERVICE: dict[str, set[str]] = {}
DEFAULTS = {
    "prompt": "Extract all data as complete as possible.",
    "html": True,
    "browser_rendering": "auto",
    "timeout": 300,
    "warm_start": False,
    "block_resources": False,
    "max_age": 0,
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
        if name in OMITTED | OMITTED_BY_SERVICE.get(operation, set()):
            assert "default" not in parameter, name
        elif name == "screenshot":
            continue
        else:
            assert parameter["default"] == DEFAULTS[name], name
        if isinstance(DEFAULTS.get(name), bool):
            assert parameter["type"] == "boolean"
    if "browser_rendering" in parameters:
        rendering = parameters["browser_rendering"]
        assert rendering["type"] == "select"
        assert [option["value"] for option in rendering["options"]] == ["auto", "true", "false"]
    bounds = {"timeout": (1, 330), "max_age": (0, 604800000), "num_results": (10, 100)}
    for name, (minimum, maximum) in bounds.items():
        if name in parameters:
            parameter = parameters[name]
            assert (parameter["type"], parameter["min"], parameter["max"]) == (
                "number",
                minimum,
                maximum,
            )
            assert parameter["precision"] == 0
    if "max_retries" in parameters:
        assert (parameters["max_retries"]["min"], parameters["max_retries"]["precision"]) == (0, 0)
        assert "max" not in parameters["max_retries"]


def test_screenshot_parameter_forms_differ_by_service() -> None:
    capture = {p["name"]: p for p in _schema("scrape_html")["parameters"]}
    extraction = {p["name"]: p for p in _schema("scrape_json")["parameters"]}
    area = {p["name"]: p for p in _schema("get_screenshot")["parameters"]}

    assert capture["screenshot"]["type"] == "string"
    assert capture["screenshot"]["default"] == "false"
    assert extraction["screenshot"]["type"] == "boolean"
    assert extraction["screenshot"]["default"] is False
    assert area["screenshot"]["type"] == "string"
    assert area["screenshot"]["default"] == "full"
    # Get screenshot always sends html=false, markdown=false, and browserRendering=true.
    assert set(area).isdisjoint({"browser_rendering", "html", "markdown"})


def test_removed_options_are_not_offered() -> None:
    removed = {"super", "wait_until", "proxy_country", "proxy", "return_cookie", "markdown"}
    removed |= {"save_result", "token_cap", "action"}
    for operation in SERVICE_DESCRIPTIONS:
        names = {parameter["name"] for parameter in _schema(operation)["parameters"]}
        assert names.isdisjoint(removed), operation
    assert "html" not in {p["name"] for p in _schema("scrape_markdown")["parameters"]}


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

    assert manifest["version"] == "0.4.0"
    assert f'version = "{manifest["version"]}"' in pyproject
    assert manifest["network"]["domains"] == ["api.app.mrscraper.com", "api.mrscraper.com"]
    assert "feat/mrscraper-0.4.0-source" in manifest["repo"]
