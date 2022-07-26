# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json

from django.http import HttpResponse
import yaml

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
        "paths": [],
        "info": {"title": "MAAS HTTP API", "version": "2.0.0"},
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
    return {
        "url": f"{maas_url}{settings.API_URL_PREFIX}",
        "description": f"{maas_name} API",
    }
