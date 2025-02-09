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
from typing import Any

from django.http import HttpResponse
from piston3.resource import Resource
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
PARAM_RE = re.compile(
    r"^{(?P<param>\S+)}$",
)

# https://github.com/canonical/maas.io/issues/806
# Match variables enclosed by :, ', ` within a docstring, variables cannot contain spaces or the
# enclosing character within their definition
MARKERS = [":", "'", "`"]
MATCHES = [re.compile(rf" {k}[^ ^{k}]*{k} ") for k in MARKERS]

NEWLINES = re.compile(r"(?<![:.])[\n]+")
WHITESPACE = re.compile(r"\n\s+")
PUNCTUATION = re.compile(r"([^\w\s])\1+")
POINTS = ["*", "+", "-"]


def landing_page(request: str) -> HttpResponse:
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


def endpoint(request: str) -> HttpResponse:
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


def get_api_landing_page() -> dict[str, str | Any]:
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
                "path": "/MAAS/docs",
                "rel": "service-doc",
                "type": "text/html",
                "title": "offline MAAS documentation",
            },
            {
                "path": f"{settings.API_URL_PREFIX}openapi.yaml",
                "rel": "service-desc",
                "type": "application/openapi+yaml",
                "title": "the OpenAPI definition",
            },
            {
                "path": "/MAAS/api/docs/",
                "rel": "service-doc",
                "type": "text/html",
                "title": "OpenAPI documentation",
            },
        ],
    }
    return description


def get_api_endpoint() -> dict[str, str | Any]:
    """Return the API endpoint"""
    description = {
        "openapi": "3.1.0",
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


def _get_maas_servers() -> list[dict[str, str]]:
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


def _new_path_item(params: list[Any]) -> dict[str, dict[str, Any]]:
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


def _prettify(doc: str) -> str:
    """Cleans up text by:
    - Dedenting text to the same depth.
    - Respecting paragraphing by not replacing newlines that occur after periods or colons
    - Removeing duplicate punctuation groups and replaces with singular
    """
    doc = dedent(doc)
    doc = NEWLINES.sub(" ", doc)
    doc = WHITESPACE.sub("\n", doc)
    doc = PUNCTUATION.sub(r"\1", doc)
    for idx, point in enumerate(POINTS):
        doc = re.sub(rf"\n\s*\{point}", f"\n{' ' * 2 * idx}{point}", doc)
    return doc.strip()


def _contains_variables(doc: str) -> list[str] | None:
    """Search for any instances of :variable:, ''variable'', or `variable`."""
    for m in MATCHES:
        if (v := m.findall(doc[doc.find(":") :])) and len(v) > 1:
            return v


def _parse_enumerable(doc: str) -> tuple[str, list[str]]:
    """Parse docstring for multiple variables. Clean up and represent as the correct
    form. (https://github.com/canonical/maas.io/issues/806)"""
    enumerable = {}
    if variables := _contains_variables(doc):
        for idx, var in enumerate(variables):
            start_pos = doc.find(var) + len(var)
            end_pos = (
                len(doc)
                if idx >= len(variables) - 1
                else doc.find(variables[idx + 1])
            )
            var_string = doc[start_pos:end_pos]
            doc = doc.replace(var + var_string, "")
            depth = MARKERS.index(var[1])
            enumerable[var.strip(var[:2]) or " "] = {
                "description": _parse_enumerable(var_string)[0],
                "point": POINTS[depth],
            }
        doc = "\n".join(
            [f"{doc}"]
            + [
                f"{v['point']} `{k}` {v['description'].strip('.,')}."
                for k, v in enumerable.items()
            ]
        )
    return doc, list(enumerable.keys())


def _render_oapi_oper_item(
    http_method: str,
    op: str,
    doc: str,
    uri_params: Any,
    function: object,
    resources: set[Resource],
) -> dict[str, str | Any]:
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
    function: object,
    http_method: str,
    uri_params: Any,
    doc: str,
    resources: set[Resource],
) -> dict[str, str | Any]:
    def _type_to_string(schema: str) -> str:
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

    def _response_pair(ap_dict: dict[str, str | Any]) -> list[str]:
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

        oper_obj["description"] = _prettify(
            _parse_enumerable(ap_dict["description"])[0]
        )

        if "deprecated" in oper_obj["description"].lower():
            oper_obj["deprecated"] = True
        for param in ap_dict["params"]:
            description = _parse_enumerable(param["description_stripped"])[0]
            # LP 2009140
            stripped_name = PARAM_RE.match(param["name"])
            name = (
                param["name"]
                if stripped_name is None
                else stripped_name.group(1)
            )
            required = (
                param["options"]["required"].lower() == "true"
                or name != param["name"]
            )
            # params with special charcters in names don't form part of the request body
            if http_method in ["GET", "DELETE"] or name != param["name"]:
                param_dict = {
                    "name": name,
                    "in": "path" if name in uri_params else "query",
                    "description": _prettify(description),
                    "schema": {
                        "type": _type_to_string(param["type"]),
                    },
                    "required": required,
                }
                oper_obj.setdefault("parameters", []).append(param_dict)
            else:
                params_dict = {
                    "description": _prettify(description),
                    "type": _type_to_string(param["type"]),
                }
                body.setdefault("properties", {})[name] = params_dict
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
                        "multipart/form-data": {
                            "schema": {**body},
                        },
                    },
                }
            }
        )

    return oper_obj


def _render_oapi_paths() -> dict[str, str | Any]:
    from maasserver import urls_api as urlconf

    def _resource_key(resource: Resource) -> str:
        return resource.handler.__class__.__name__

    def _export_key(
        export: tuple[tuple[str, str], object],
    ) -> tuple[str, object]:
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
