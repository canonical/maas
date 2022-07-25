# Copyright 2014-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json

from django.http import HttpResponse
import yaml

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
    doc = description["externalDocs"]
    doc["url"] = build_absolute_uri(request, doc["url"])
    # Return as a YAML document
    return HttpResponse(
        yaml.dump(description),
        content_type="application/yaml",
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
                "path": "/MAAS/api/2.0/openapi.yaml",
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
        "info": {"title": "MAAS OpenApi Endpoint", "version": "1.0.0"},
        "paths": [],
        "externalDocs": {
            "description": "MAAS API documentation",
            "url": "/MAAS/docs/api.html",
        },
    }
    return description
