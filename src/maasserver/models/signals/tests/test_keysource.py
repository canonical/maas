# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of keysource signals."""


import random

from maasserver.enum import KEYS_PROTOCOL_TYPE
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestDeleteKeySourceWhenNoMoreKeys(MAASServerTestCase):
    """Test `KeySource` instances deleted when no more `SSHKey`s."""

    def test_delete_keysource_deleted_when_no_more_keys(self):
        user = factory.make_User()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        keysource = factory.make_KeySource(protocol=protocol, auth_id=auth_id)
        sshkey = factory.make_SSHKey(user=user, keysource=keysource)
        sshkey.delete()
        self.assertIsNone(reload_object(keysource))

    def test_do_not_delete_keysource_when_keys(self):
        user = factory.make_User()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        keysource = factory.make_KeySource(protocol=protocol, auth_id=auth_id)
        factory.make_SSHKey(user=user, keysource=keysource)
        self.assertIsNotNone(reload_object(keysource))
