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
from apiclient.testing.credentials import make_api_credentials
from fixtures import EnvironmentVariableFixture
from maastesting.factory import factory
from provisioningserver import (
    auth,
    cache,
    )
from provisioningserver.testing.testcase import PservTestCase


class TestAuth(PservTestCase):

    def test_record_api_credentials_records_credentials_string(self):
        creds_string = convert_tuple_to_string(make_api_credentials())
        auth.record_api_credentials(creds_string)
        self.assertEqual(
            creds_string, cache.cache.get(auth.API_CREDENTIALS_CACHE_KEY))

    def test_get_recorded_api_credentials_returns_credentials_as_tuple(self):
        creds = make_api_credentials()
        auth.record_api_credentials(convert_tuple_to_string(creds))
        self.assertEqual(creds, auth.get_recorded_api_credentials())

    def test_get_recorded_api_credentials_returns_None_without_creds(self):
        self.assertIsNone(auth.get_recorded_api_credentials())

    def test_get_recorded_nodegroup_uuid_vs_record_nodegroup_uuid(self):
        nodegroup_uuid = factory.make_name('nodegroupuuid')
        auth.record_nodegroup_uuid(nodegroup_uuid)
        self.assertEqual(nodegroup_uuid, auth.get_recorded_nodegroup_uuid())

    def test_get_recorded_maas_url_uses_environment_override(self):
        required_url = factory.make_name("MAAS_URL")
        self.useFixture(EnvironmentVariableFixture("MAAS_URL", required_url))
        self.assertEqual(required_url, auth.get_recorded_maas_url())
