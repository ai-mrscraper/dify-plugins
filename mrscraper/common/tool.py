from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from common.client import MrscraperClient


class MrscraperTool(Tool):
    def _client(self) -> MrscraperClient:
        token = self.runtime.credentials.get("api_token")
        return MrscraperClient(token if isinstance(token, str) else "")

    def _messages(self, data: Any) -> Generator[ToolInvokeMessage, None, None]:
        if isinstance(data, dict | list):
            yield self.create_json_message(data)
        else:
            yield self.create_text_message(data if isinstance(data, str) else json.dumps(data))
