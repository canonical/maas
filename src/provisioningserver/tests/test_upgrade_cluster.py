# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `upgrade-cluster` command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from argparse import ArgumentParser

from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import Mock
from provisioningserver import upgrade_cluster


class TestUpgradeCluster(MAASTestCase):

    def run_command(self):
        parser = ArgumentParser()
        upgrade_cluster.add_arguments(parser)
        upgrade_cluster.run(parser.parse_args(()))

    def patch_upgrade_hooks(self, hooks=None):
        """Temporarily replace the upgrade hooks."""
        if hooks is None:
            hooks = []
        self.patch(upgrade_cluster, 'UPGRADE_HOOKS', hooks)

    def test_calls_hooks(self):
        upgrade_hook = Mock()
        self.patch_upgrade_hooks([upgrade_hook])
        self.run_command()
        self.assertThat(upgrade_hook, MockCalledOnceWith())

    def test_calls_hooks_in_order(self):
        calls = []

        # Define some hooks.  They will be run in the order in which they are
        # listed (not in the order in which they are defined, or alphabetical
        # order, or any other order).

        def last_hook():
            calls.append('last')

        def first_hook():
            calls.append('first')

        def middle_hook():
            calls.append('middle')

        self.patch_upgrade_hooks([first_hook, middle_hook, last_hook])
        self.run_command()
        self.assertEqual(['first', 'middle', 'last'], calls)
