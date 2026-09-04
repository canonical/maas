# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi.responses import HTMLResponse

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.constants import API_PREFIX

# Swagger UI assets served locally from snap (see snap/snapcraft.yaml for build details)
_SWAGGER_UI_CSS_URL = "/MAAS/swagger-ui/swagger-ui.css"
_SWAGGER_UI_JS_URL = "/MAAS/swagger-ui/swagger-ui-bundle.js"
_SWAGGER_UI_INIT_URL = "/MAAS/swagger-ui/swagger-ui-init.js"
# Reuse the MAAS UI favicon which is already served locally via the /MAAS/r/
# static location. This avoids the default fastapi.tiangolo.com favicon fetch.
_SWAGGER_UI_FAVICON_URL = "/MAAS/r/maas-favicon-32px.png"


def _render_swagger_ui_html(*, title: str, openapi_url: str) -> str:
    """Render the Swagger UI HTML without any inline scripts.

    FastAPI's built-in ``get_swagger_ui_html`` emits an inline ``<script>``
    block to bootstrap Swagger UI, which is incompatible with a strict CSP
    (``script-src 'self'``). This helper produces the same page but sources
    the bootstrap from an external file, ``swagger-ui-init.js``, which is
    also served locally.

    The OpenAPI URL is passed to the bootstrap via a ``data-openapi-url``
    attribute on the ``<script>`` tag, so no inline JS is needed to configure
    it.
    """
    return f"""\
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <link rel="icon" type="image/png" href="{_SWAGGER_UI_FAVICON_URL}">
    <link rel="stylesheet" type="text/css" href="{_SWAGGER_UI_CSS_URL}">
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="{_SWAGGER_UI_JS_URL}"></script>
    <script src="{_SWAGGER_UI_INIT_URL}" data-openapi-url="{openapi_url}"></script>
  </body>
</html>
"""


class SwaggerHandler(Handler):
    @handler(path="/docs", methods=["GET"], include_in_schema=False)
    async def custom_swagger_ui_html(self):
        return HTMLResponse(
            _render_swagger_ui_html(
                title="MAAS API V3 - Swagger UI",
                openapi_url=f"{API_PREFIX}/openapi.json",
            )
        )
