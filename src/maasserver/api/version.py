# Copyright 2014 Canonical Ltd.  This software is licensed under the
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

# MAAS capabilities. See docs/capabilities.rst for documentation.
CAP_NETWORKS_MANAGEMENT = 'networks-management'
CAP_STATIC_IPADDRESSES = 'static-ipaddresses'

API_CAPABILITIES_LIST = [
    CAP_NETWORKS_MANAGEMENT,
    CAP_STATIC_IPADDRESSES,
    ]


class VersionHandler(AnonymousOperationsHandler):
    """Information about this MAAS instance.

    This returns a JSON dictionary with information about this
    MAAS instance.
    {
        'capabilities': ['capability1', 'capability2', ...]
    }
    """
    api_doc_section_name = "MAAS version"
    create = update = delete = None

    def read(self, request):
        version_info = {
            'capabilities': API_CAPABILITIES_LIST,
        }
        return HttpResponse(
            version_info, mimetype='application/json; charset=utf-8',
            status=httplib.OK)
