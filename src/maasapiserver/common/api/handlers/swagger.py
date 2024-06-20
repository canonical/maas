from fastapi.openapi.docs import get_swagger_ui_html

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.constants import API_PREFIX


class SwaggerHandler(Handler):
    @handler(path="/docs", methods=["GET"], include_in_schema=False)
    async def custom_swagger_ui_html(self):
        return get_swagger_ui_html(
            openapi_url=f"{API_PREFIX}/openapi.json",
            title="MAAS API V3 - Swagger UI",
        )
