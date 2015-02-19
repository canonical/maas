# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.cluster_config`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from fixtures import EnvironmentVariableFixture
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.cluster_config import (
    get_cluster_uuid,
    get_cluster_variable,
    get_maas_url,
    )


class TestClusterConfig(MAASTestCase):

    def test_get_cluster_variable_reads_env(self):
        var = factory.make_name('variable')
        value = factory.make_name('value')
        self.useFixture(EnvironmentVariableFixture(var, value))
        self.assertEqual(value, get_cluster_variable(var))

    def test_get_cluster_variable_fails_if_not_set(self):
        self.assertRaises(
            AssertionError,
            get_cluster_variable, factory.make_name('nonexistent-variable'))
