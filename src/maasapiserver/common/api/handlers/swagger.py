from fastapi.openapi.docs import get_swagger_ui_html

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.settings import api_prefix_path


class SwaggerHandler(Handler):
    @handler(path="/docs", methods=["GET"], include_in_schema=False)
    async def custom_swagger_ui_html(self):
        return get_swagger_ui_html(
            # There is an nginx proxy in front of this application. Keep it in sync with src/maasserver/templates/http/regiond.nginx.conf.template
            openapi_url=f"{api_prefix_path()}/openapi.json",
            title="MAAS API V3 - Swagger UI",
        )
