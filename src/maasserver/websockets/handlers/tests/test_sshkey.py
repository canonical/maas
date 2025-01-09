# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.sshkey`"""


from maasserver.models.event import Event
from maasserver.models.sshkey import SSHKey
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.keys import ImportSSHKeysError
from maasserver.utils.orm import get_one
from maasserver.websockets.base import HandlerDoesNotExistError, HandlerError
from maasserver.websockets.handlers.sshkey import SSHKeyHandler
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from provisioningserver.events import AUDIT


class TestSSHKeyHandler(MAASServerTestCase):
    def dehydrate_sshkey(self, sshkey):
        keysource = None
        if sshkey.protocol is not None and sshkey.auth_id is not None:
            keysource = {
                "protocol": sshkey.protocol,
                "auth_id": sshkey.auth_id,
            }
        data = {
            "id": sshkey.id,
            "display": sshkey.display_html(70),
            "user": sshkey.user.id,
            "key": sshkey.key,
            "keysource": keysource,
            "updated": dehydrate_datetime(sshkey.updated),
            "created": dehydrate_datetime(sshkey.created),
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = SSHKeyHandler(user, {}, None)
        sshkey = factory.make_SSHKey(user)
        self.assertEqual(
            self.dehydrate_sshkey(sshkey), handler.get({"id": sshkey.id})
        )

    def test_get_doesnt_work_if_not_owned(self):
        user = factory.make_User()
        handler = SSHKeyHandler(user, {}, None)
        not_owned_sshkey = factory.make_SSHKey(factory.make_User())
        self.assertRaises(
            HandlerDoesNotExistError, handler.get, {"id": not_owned_sshkey.id}
        )

    def test_list(self):
        user = factory.make_User()
        handler = SSHKeyHandler(user, {}, None)
        factory.make_SSHKey(user)
        expected_sshkeys = [
            self.dehydrate_sshkey(sshkey) for sshkey in SSHKey.objects.all()
        ]
        self.assertCountEqual(expected_sshkeys, handler.list({}))

    def test_create(self):
        user = factory.make_User()
        handler = SSHKeyHandler(user, {}, None)
        key_string = get_data("data/test_rsa0.pub")
        new_sshkey = handler.create({"key": key_string})
        self.assertEqual(new_sshkey.get("user"), user.id)
        self.assertEqual(new_sshkey.get("key"), key_string)

    def test_delete(self):
        user = factory.make_User()
        sshkey = factory.make_SSHKey(user=user)
        handler = SSHKeyHandler(user, {}, None)
        handler.delete({"id": sshkey.id})
        self.assertIsNone(get_one(SSHKey.objects.filter(id=sshkey.id)))

    def test_import_keys_calls_save_keys_for_user_and_create_audit_event(self):
        user = factory.make_User()
        handler = SSHKeyHandler(user, {}, None)
        protocol = factory.make_name("protocol")
        auth_id = factory.make_name("auth")
        mock_save_keys = self.patch(SSHKey.objects, "from_keysource")
        handler.import_keys({"protocol": protocol, "auth_id": auth_id})
        mock_save_keys.assert_called_once_with(
            user=user, protocol=protocol, auth_id=auth_id
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Imported SSH keys.")

    def test_import_keys_raises_HandlerError(self):
        user = factory.make_User()
        handler = SSHKeyHandler(user, {}, None)
        protocol = factory.make_name("protocol")
        auth_id = factory.make_name("auth")
        mock_save_keys = self.patch(SSHKey.objects, "from_keysource")
        mock_save_keys.side_effect = ImportSSHKeysError()
        self.assertRaises(
            HandlerError,
            handler.import_keys,
            {"protocol": protocol, "auth_id": auth_id},
        )
