# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for sshkeys import action."""


import random
from unittest.mock import Mock

from apiclient.testing.credentials import make_api_credentials
from maascli.actions.sshkeys_import import SSHKeysImportAction
from maascli.command import CommandError
from maasserver.enum import KEYS_PROTOCOL_TYPE
from maastesting.factory import factory
from maastesting.fixtures import CaptureStandardIO
from maastesting.testcase import MAASTestCase


class TestSSHKeysImportAction(MAASTestCase):
    """Tests for `SSHKeysImportAction`."""

    def make_sshkeys_import_action(self):
        self.stdio = self.useFixture(CaptureStandardIO())
        action_bases = (SSHKeysImportAction,)
        action_ns = {
            "action": {"method": "POST"},
            "handler": {"uri": b"/MAAS/api/2.0/sshkeys/", "params": []},
            "profile": {"credentials": make_api_credentials()},
        }
        action_class = type("import", action_bases, action_ns)
        action = action_class(Mock())
        return action

    def test_name_value_pair_returns_sshkey_creds_tuple(self):
        action = self.make_sshkeys_import_action()
        ks = "{}:{}".format(
            random.choice([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]),
            factory.make_name("user-id"),
        )
        expected_data = ("keysource", ks)
        data = action.name_value_pair(ks)
        self.assertEqual(data, expected_data)

    def test_name_value_pair_returns_sshkey_creds_tuple_for_no_protocol(self):
        action = self.make_sshkeys_import_action()
        ks = factory.make_name("user-id")
        expected_data = ("keysource", ks)
        data = action.name_value_pair(ks)
        self.assertEqual(data, expected_data)

    def test_name_value_pair_returns_sshkey_creds_tuple_for_no_input(self):
        action = self.make_sshkeys_import_action()
        self.assertRaises(CommandError, action.name_value_pair, "")
