# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: API Version."""

import http.client
import json

from django.http import HttpResponse

from maasserver.api.support import AnonymousOperationsHandler
from maasserver.models.controllerinfo import get_maas_version

# MAAS capabilities. See docs/version.rst for documentation.
CAP_NETWORKS_MANAGEMENT = "networks-management"
CAP_STATIC_IPADDRESSES = "static-ipaddresses"
CAP_IPv6_DEPLOYMENT_UBUNTU = "ipv6-deployment-ubuntu"
CAP_DEVICES_MANAGEMENT = "devices-management"
CAP_STORAGE_DEPLOYMENT_UBUNTU = "storage-deployment-ubuntu"
CAP_NETWORK_DEPLOYMENT_UBUNTU = "network-deployment-ubuntu"
CAP_BRIDGING_INTERFACE_UBUNTU = "bridging-interface-ubuntu"
CAP_BRIDGING_AUTOMATIC_UBUNTU = "bridging-automatic-ubuntu"
CAP_AUTHENTICATE_API = "authenticate-api"

API_CAPABILITIES_LIST = [
    CAP_NETWORKS_MANAGEMENT,
    CAP_STATIC_IPADDRESSES,
    CAP_IPv6_DEPLOYMENT_UBUNTU,
    CAP_DEVICES_MANAGEMENT,
    CAP_STORAGE_DEPLOYMENT_UBUNTU,
    CAP_NETWORK_DEPLOYMENT_UBUNTU,
    CAP_BRIDGING_INTERFACE_UBUNTU,
    CAP_BRIDGING_AUTOMATIC_UBUNTU,
    CAP_AUTHENTICATE_API,
]


class VersionHandler(AnonymousOperationsHandler):
    """Information about this MAAS instance."""

    api_doc_section_name = "MAAS version"
    create = update = delete = None

    def read(self, request):
        """@description-title MAAS version information
        @description Read version and capabilities of this MAAS instance.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing MAAS version
        and capabilities information.
        @success-example "success-json" [exkey=version] placeholder text
        """
        version_info = {
            "capabilities": API_CAPABILITIES_LIST,
            "version": str(get_maas_version()),
            "subversion": "",  # unused, kept for API compatibility
        }
        return HttpResponse(
            json.dumps(version_info),
            content_type="application/json; charset=utf-8",
            status=int(http.client.OK),
        )

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("version_handler", [])
