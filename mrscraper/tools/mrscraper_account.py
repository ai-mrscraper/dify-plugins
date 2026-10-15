from collections.abc import Generator
from typing import Any

from dify_plugin.entities.tool import ToolInvokeMessage

import common.tool
from common.parameters import account_parameters


class MrscraperAccountTool(common.tool.MrscraperTool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        parameters = account_parameters(tool_parameters)
        yield from self._messages(self._client().invoke("account", parameters))
