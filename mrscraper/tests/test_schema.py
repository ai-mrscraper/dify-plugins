from pathlib import Path

import yaml
from dify_plugin import Tool
from dify_plugin.core.utils.class_loader import load_single_subclass_from_source
from dify_plugin.entities.tool import ToolParameter

ROOT = Path(__file__).parents[1]
TOOL_NAMES = ("mrscraper_account", "mrscraper_scraper_api", "mrscraper_web_search")


def test_provider_registers_exactly_three_renderable_tool_schemas() -> None:
    provider = yaml.safe_load((ROOT / "provider/mrscraper.yaml").read_text())

    assert set(provider["tools"]) == {f"tools/{name}.yaml" for name in TOOL_NAMES}
    assert len(provider["tools"]) == 3
    assert {path.stem for path in (ROOT / "tools").glob("*.yaml")} == set(TOOL_NAMES)
    for name in TOOL_NAMES:
        schema = yaml.safe_load((ROOT / f"tools/{name}.yaml").read_text())
        assert schema["identity"]["name"] == name
        assert schema["extra"]["python"]["source"] == f"tools/{name}.py"
        for parameter in schema.get("parameters", []):
            ToolParameter.model_validate(parameter)


def test_each_registered_source_loads_a_single_tool_subclass() -> None:
    expected = ("MrscraperAccountTool", "MrscraperScraperApiTool", "MrscraperWebSearchTool")
    for name, class_name in zip(TOOL_NAMES, expected, strict=True):
        tool_class = load_single_subclass_from_source(
            module_name=f"test_{name}",
            script_path=str(ROOT / f"tools/{name}.py"),
            parent_type=Tool,
        )
        assert tool_class.__name__ == class_name


def test_scraper_tristate_and_json_header_controls_are_renderer_safe() -> None:
    schema = yaml.safe_load((ROOT / "tools/mrscraper_scraper_api.yaml").read_text())
    parameters = {parameter["name"]: parameter for parameter in schema["parameters"]}

    for name in ("browser_rendering", "stream"):
        parameter = parameters[name]
        assert parameter["type"] == "select"
        assert parameter["default"] == "auto"
        assert {option["value"] for option in parameter["options"]} == {"auto", "true", "false"}
    assert parameters["headers"]["type"] == "string"
    assert parameters["html"]["default"] is True


def test_search_defaults_explain_the_sdk_raw_html_behavior() -> None:
    schema = yaml.safe_load((ROOT / "tools/mrscraper_web_search.yaml").read_text())
    parameters = {parameter["name"]: parameter for parameter in schema["parameters"]}

    assert parameters["raw"]["default"] is True
    assert parameters["format"]["default"] == "json"
    assert parameters["timeout"]["default"] == 600
