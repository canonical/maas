# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS OpenAPI definition.

This definition follows the rules and limitations of the ReST documentation.
(see doc.py and doc_handler.py).
"""

import json
from textwrap import dedent

from django.http import HttpResponse
import yaml

from maasserver.api import support
from maasserver.api.doc import find_api_resources, generate_doc
from maasserver.djangosettings import settings
from maasserver.models.config import Config
from maasserver.utils import build_absolute_uri


def landing_page(request):
    """Render a landing page with pointers for the MAAS API.

    :return: An `HttpResponse` containing a JSON page with pointers to both
        human-readable documentation and api definitions.
    """
    description = get_api_landing_page()
    for link in description["resources"]:
        link["href"] = build_absolute_uri(request, link["path"])
    # Return as a JSON document
    return HttpResponse(
        json.dumps(description),
        content_type="application/json",
    )


def endpoint(request):
    """Render the OpenApi endpoint.

    :return: An `HttpResponse` containing a YAML document that complies
        with the OpenApi spec 3.0.
    """
    description = get_api_endpoint()
    # Return as a YAML document
    return HttpResponse(
        yaml.dump(description),
        content_type="application/openapi+yaml",
    )


def get_api_landing_page():
    """Return the API landing page"""
    description = {
        "title": "MAAS API",
        "description": "API landing page for MAAS",
        "resources": [
            {
                "path": "/MAAS/api",
                "rel": "self",
                "type": "application/json",
                "title": "this document",
            },
            {
                "path": f"{settings.API_URL_PREFIX}/openapi.yaml",
                "rel": "service-desc",
                "type": "application/openapi+yaml",
                "title": "the API definition",
            },
            {
                "path": "/MAAS/docs/api.html",
                "rel": "service-doc",
                "type": "text/html",
                "title": "the API documentation",
            },
        ],
    }
    return description


def get_api_endpoint():
    """Return the API endpoint"""
    description = {
        "openapi": "3.0.0",
        "info": {"title": "MAAS HTTP API", "version": "2.0.0"},
        "paths": _render_oapi_paths(),
        "externalDocs": {
            "description": "MAAS API documentation",
            "url": "/MAAS/docs/api.html",
        },
    }
    description["servers"] = _get_maas_servers()
    return description


def _get_maas_servers():
    """Return a servers defintion of the public-facing MAAS address.

    :return: An object describing the MAAS public-facing server.
    """
    maas_url = (
        Config.objects.get_config("maas_url").rstrip("/").removesuffix("/MAAS")
    )
    maas_name = Config.objects.get_config("maas_name")
    return [
        {
            "url": f"{maas_url}{settings.API_URL_PREFIX}",
            "description": f"{maas_name} API",
        },
    ]


def _new_path_item(doc):
    path_item = {}
    (_, params) = doc.handler.resource_uri()
    for p in params:
        path_item.setdefault("parameters", []).append(
            {
                "name": p,
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            }
        )
    return path_item


def _render_oapi_oper_item(http_method, op, doc, function):
    oper_id = op or support.OperationsResource.crudmap.get(http_method)
    oper_obj = {
        "operationId": f"{doc.name}_{oper_id}",
        "tags": [doc.handler.api_doc_section_name],
        "summary": f"{doc.name} {oper_id}",
        "description": dedent(doc.doc).strip(),
        "responses": {},
    }
    # TODO add requestBody

    # TODO add actual responses, this 'default' is just to make the linter happy for now
    oper_obj["responses"].update(
        {
            "default": {
                "description": "default response",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "additionalProperties": True,
                        }
                    },
                },
            }
        }
    )

    return oper_obj


def _render_oapi_paths():
    from maasserver import urls_api as urlconf

    def _resource_key(resource):
        return resource.handler.__class__.__name__

    def _export_key(export):
        (http_method, op), function = export
        return http_method, op or "", function

    resources = find_api_resources(urlconf)
    paths = {}

    for res in sorted(resources, key=_resource_key):
        handler = type(res.handler)
        doc = generate_doc(handler)
        uri = doc.resource_uri_template
        exports = handler.exports.items()

        for (http_method, op), function in sorted(exports, key=_export_key):
            oper_uri = f"{uri}?op={op}" if op else uri
            path_item = paths.setdefault(
                f"/{oper_uri.removeprefix(settings.API_URL_PREFIX)}",
                _new_path_item(doc),
            )
            path_item[http_method.lower()] = _render_oapi_oper_item(
                http_method, op, doc, function
            )
    return paths
