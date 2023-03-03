# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS OpenAPI definition.

This definition follows the rules and limitations of the ReST documentation.
(see doc.py and doc_handler.py).
"""

from inspect import getdoc, signature
import json
import re
from textwrap import dedent

from django.http import HttpResponse
import yaml

from maasserver.api import support
from maasserver.api.annotations import APIDocstringParser
from maasserver.api.doc import find_api_resources, generate_doc
from maasserver.djangosettings import settings
from maasserver.models.config import Config
from maasserver.utils import build_absolute_uri

# LP 2009140: Match a par of brackets enclosing a string, return only the string within the brackets.
# Functions as a more context aware equivalent to string.strip("}{")
# ie: '{param}' returns 'param', 'param_{test}' is unnafected
PARAM_RE = re.compile(r"(?<=\{)\.+(?<=\})")


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
    description["servers"] = _get_maas_servers()
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
                "path": f"{settings.API_URL_PREFIX}openapi.yaml",
                "rel": "service-desc",
                "type": "application/openapi+yaml",
                "title": "the API definition",
            },
            {
                "path": "/MAAS/api/docs/",
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
        "info": {
            "title": "MAAS HTTP API",
            "description": "This is the documentation for the API that lets you control and query MAAS. You can find out more about MAAS at [https://maas.io/](https://maas.io/).",
            "version": "2.0.0",
            "license": {
                "name": "GNU Affero General Public License version 3",
                "url": "https://www.gnu.org/licenses/agpl-3.0.en.html",
            },
        },
        "paths": _render_oapi_paths(),
        "externalDocs": {
            "description": "MAAS API documentation",
            "url": "/MAAS/docs/api.html",
        },
    }
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


def _new_path_item(params):
    path_item = {}
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


def _prettify(doc):
    """Cleans up text by replacing newlines with spaces, so that sentences are
    not broken apart prematurely.
    Respects paragraphing by not replacing newlines that occur after periods.
    """
    return re.sub("(?<![.\n])[\n]+", " ", dedent(doc)).strip()


def _render_oapi_oper_item(
    http_method, op, doc, uri_params, function, resources
):
    oper_id = op or support.OperationsResource.crudmap.get(http_method)
    oper_obj = {
        "operationId": f"{doc.name}_{oper_id}",
        "tags": [doc.handler.api_doc_section_name],
        "summary": f"{doc.name} {oper_id}",
        "description": _prettify(doc.doc),
        "responses": {},
    }
    oper_docstring = _oapi_item_from_docstring(
        function, http_method, uri_params, doc, resources
    )
    # Only overwrite the values that are non-blank
    oper_obj.update({k: v for k, v in oper_docstring.items() if v})
    return oper_obj


def _oapi_item_from_docstring(
    function, http_method, uri_params, doc, resources
):
    def _type_to_string(schema):
        match schema:
            case "Boolean":
                return "boolean"
            case "Float":
                return "number"
            case "Int":
                return "integer"
            case "String":
                return "string"
            case _:
                return "object"

    def _response_pair(ap_dict):
        status_code = "HTTP Status Code"
        status = content = {}
        paired = []
        for response in reversed(ap_dict["errors"] + ap_dict["successes"]):
            if response["type"] == status_code:
                status = response
                if content in paired:
                    content = {}
                paired.extend([status, content])
            else:
                content = response
        # edge case where a response is not given in the docstring
        if paired == [] and content:
            paired.extend([content, content])
        paired = iter(paired)
        return zip(paired, paired)

    oper_obj = {}
    body = {
        "type": "object",
        "additionalProperties": {"type": "string"},
    }
    ap = APIDocstringParser()
    docstring = getdoc(function)
    if docstring and ap.is_annotated_docstring(docstring):
        ap.parse(docstring)
        ap_dict = ap.get_dict()
        oper_obj["summary"] = ap_dict["description_title"].strip()
        oper_obj["description"] = _prettify(ap_dict["description"])
        if "deprecated" in oper_obj["description"].lower():
            oper_obj["deprecated"] = True
        for param in ap_dict["params"]:
            description = _prettify(param["description_stripped"])
            # LP 2009140
            stripped_name = PARAM_RE.match(param["name"])
            name = (
                param["name"] if not stripped_name else stripped_name.group()
            )
            required = (
                param["options"]["required"].lower() == "true"
                or name != param["name"]
            )
            # params with special charcters in names don't form part of the request body
            if name != param["name"]:
                param_dict = {
                    "name": name,
                    "in": "path" if name in uri_params else "query",
                    "description": description,
                    "schema": {
                        "type": _type_to_string(param["type"]),
                    },
                    "required": required,
                }
                oper_obj.setdefault("parameters", []).append(param_dict)
            else:
                body.setdefault("properties", {})[name] = {
                    "description": description,
                    "type": _type_to_string(param["type"]),
                }
                if required:
                    body.setdefault("required", []).append(name)

        for status, content in _response_pair(ap_dict):
            response = {
                "description": _prettify(
                    content.get(
                        "description_stripped", status["description_stripped"]
                    )
                ),
            }
            match content.get("type", "").lower():
                case "content":
                    response["content"] = {
                        "text/plain": {
                            "schema": {"type": "string"},
                        },
                    }
                case "json":
                    response["content"] = {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                        },
                    }
                case "bson":
                    response["content"] = {
                        "application/bson": {
                            "schema": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                        },
                    }

            status_code = status["name"]
            if not status_code.isdigit():
                status_code = (
                    "200" if "success" in status_code.lower() else "404"
                )
            oper_obj.setdefault("responses", {}).update(
                {status_code: response},
            )

    # populate deprecated functions properties using their replacement
    if (
        replacement_method := getattr(function, "deprecated", function)
    ) is not function:
        oper_obj["deprecated"] = True
        oper_obj["responses"] = _oapi_item_from_docstring(
            replacement_method, http_method, uri_params, doc, resources
        )["responses"]

    # if a response is still empty, query the function
    if not oper_obj.get("responses"):
        # fetch a response by calling the function
        status, msg = "200", ""
        try:
            msg = function(*[""] * len(signature(function).parameters))
        except Exception as e:
            status = "404"
            msg = str(e)
        oper_obj["responses"] = {
            status: {
                "content": {"text/plain": {"schema": {"type": "string"}}},
                "description": msg,
            }
        }

    if body.get("properties"):
        oper_obj.update(
            {
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {**body},
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
        (_, params) = doc.handler.resource_uri()

        for (http_method, op), function in sorted(exports, key=_export_key):
            oper_uri = f"{uri}op-{op}" if op else uri
            path_item = paths.setdefault(
                f"/{oper_uri.removeprefix(settings.API_URL_PREFIX)}",
                _new_path_item(params),
            )
            path_item[http_method.lower()] = _render_oapi_oper_item(
                http_method, op, doc, params, function, resources
            )
    return paths
