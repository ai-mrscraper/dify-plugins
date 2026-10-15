from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from common.client import MrscraperAPIError, MrscraperClient


class MrscraperProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        token = credentials.get("api_token")
        try:
            MrscraperClient(token if isinstance(token, str) else "").invoke("account", {})
        except MrscraperAPIError as exc:
            raise ToolProviderCredentialValidationError(str(exc)) from None
