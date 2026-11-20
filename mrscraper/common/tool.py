from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from common.client import MrscraperClient
from common.parameters import PARAMETERS


class MrscraperTool(Tool):
    def _client(self) -> MrscraperClient:
        token = self.runtime.credentials.get("api_token")
        return MrscraperClient(token if isinstance(token, str) else "")

    def _run(
        self, operation: str, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        # Validate every input before any HTTP request is made.
        parameters = PARAMETERS[operation](tool_parameters)
        yield from self._messages(self._client().invoke(operation, parameters))

    def _messages(self, data: Any) -> Generator[ToolInvokeMessage, None, None]:
        if isinstance(data, dict | list):
            yield self.create_json_message(data)
        elif isinstance(data, bytes):
            yield self.create_blob_message(data, meta={"mime_type": "application/octet-stream"})
        else:
            yield self.create_text_message(data if isinstance(data, str) else json.dumps(data))
