# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for management of node-group workers' API credentials."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from apiclient.creds import convert_tuple_to_string
from maastesting.factory import factory
from provisioningserver import auth
from provisioningserver.cache import cache
from provisioningserver.testing.testcase import PservTestCase


def make_credentials():
    """Produce a tuple of API credentials."""
    return (
        factory.make_name('consumer-key'),
        factory.make_name('resource-token'),
        factory.make_name('resource-secret'),
        )


class TestAuth(PservTestCase):

    def test_record_api_credentials_records_credentials_string(self):
        creds_string = convert_tuple_to_string(make_credentials())
        auth.record_api_credentials(creds_string)
        self.assertEqual(
            creds_string, cache.get(auth.API_CREDENTIALS_KEY_CACHE_NAME))

    def test_get_recorded_api_credentials_returns_credentials_as_tuple(self):
        creds = make_credentials()
        auth.record_api_credentials(convert_tuple_to_string(creds))
        self.assertEqual(creds, auth.get_recorded_api_credentials())

    def test_get_recorded_api_credentials_returns_None_without_creds(self):
        self.assertIsNone(auth.get_recorded_api_credentials())

    def test_get_recorded_nodegroup_name_vs_record_nodegroup_name(self):
        nodegroup_name = factory.make_name('nodegroup')
        auth.record_nodegroup_name(nodegroup_name)
        self.assertEqual(nodegroup_name, auth.get_recorded_nodegroup_name())
