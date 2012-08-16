# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.remote`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from provisioningserver.interfaces import (
    IProvisioningAPI,
    IProvisioningAPI_XMLRPC,
    )
from provisioningserver.remote import ProvisioningAPI_XMLRPC
from testtools import TestCase
from testtools.deferredruntest import SynchronousDeferredRunTest
from zope.interface.verify import verifyObject


class TestProvisioningAPI_XMLRPC(TestCase):
    """Tests for `provisioningserver.remote.ProvisioningAPI_XMLRPC`."""

    run_tests_with = SynchronousDeferredRunTest

    def test_ProvisioningAPI_init(self):
        dummy_session = object()
        papi_xmlrpc = ProvisioningAPI_XMLRPC(dummy_session)
        self.assertIs(dummy_session, papi_xmlrpc.session)
        self.assertTrue(papi_xmlrpc.allowNone)
        self.assertTrue(papi_xmlrpc.useDateTime)

    def test_ProvisioningAPI_interfaces(self):
        dummy_session = object()
        papi_xmlrpc = ProvisioningAPI_XMLRPC(dummy_session)
        verifyObject(IProvisioningAPI, papi_xmlrpc)
        verifyObject(IProvisioningAPI_XMLRPC, papi_xmlrpc)
