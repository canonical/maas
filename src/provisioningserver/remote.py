# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Provisioning API over XML-RPC."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "ProvisioningAPI_XMLRPC",
    ]

from provisioningserver.api import ProvisioningAPI
from provisioningserver.interfaces import (
    IProvisioningAPI,
    IProvisioningAPI_XMLRPC,
    )
from provisioningserver.utils import xmlrpc_export
from twisted.web.xmlrpc import XMLRPC
from zope.interface import implements


@xmlrpc_export(IProvisioningAPI)
class ProvisioningAPI_XMLRPC(XMLRPC, ProvisioningAPI):

    implements(IProvisioningAPI_XMLRPC)

    def __init__(self, session):
        XMLRPC.__init__(self, allowNone=True, useDateTime=True)
        ProvisioningAPI.__init__(self, session)
