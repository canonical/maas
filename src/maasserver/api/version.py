# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handler: API Version."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'VersionHandler',
    ]

import httplib

from django.http import HttpResponse
from maasserver.api.support import AnonymousOperationsHandler
from maasserver.utils.version import get_maas_version_subversion

# MAAS capabilities. See docs/version.rst for documentation.
CAP_NETWORKS_MANAGEMENT = 'networks-management'
CAP_STATIC_IPADDRESSES = 'static-ipaddresses'
CAP_IPv6_DEPLOYMENT_UBUNTU = 'ipv6-deployment-ubuntu'
CAP_DEVICES_MANAGEMENT = 'devices-management'
CAP_STORAGE_DEPLOYMENT = 'storage-deployment'

API_CAPABILITIES_LIST = [
    CAP_NETWORKS_MANAGEMENT,
    CAP_STATIC_IPADDRESSES,
    CAP_IPv6_DEPLOYMENT_UBUNTU,
    CAP_DEVICES_MANAGEMENT,
    CAP_STORAGE_DEPLOYMENT
    ]


class VersionHandler(AnonymousOperationsHandler):
    """Information about this MAAS instance.

    This returns a JSON dictionary with information about this
    MAAS instance::

        {
            'version': '1.8.0',
            'subversion': 'alpha10+bzr3750',
            'capabilities': ['capability1', 'capability2', ...]
        }
    """
    api_doc_section_name = "MAAS version"
    create = update = delete = None

    def read(self, request):
        """Version and capabilities of this MAAS instance."""
        version, subversion = get_maas_version_subversion()
        version_info = {
            'capabilities': API_CAPABILITIES_LIST,
            'version': version,
            'subversion': subversion,

        }
        return HttpResponse(
            version_info, mimetype='application/json; charset=utf-8',
            status=httplib.OK)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('version_handler', [])
