from collections.abc import Generator
from typing import Any

from dify_plugin.entities.tool import ToolInvokeMessage

import common.tool
from common.parameters import search_parameters


class MrscraperWebSearchTool(common.tool.MrscraperTool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        parameters = search_parameters(tool_parameters)
        yield from self._messages(self._client().invoke("web_search", parameters))
