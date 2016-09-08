# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.sshkey`"""

__all__ = []

from maasserver.models.sshkey import SSHKey
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one
from maasserver.websockets.handlers.sshkey import SSHKeyHandler
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from testtools.matchers import (
    ContainsDict,
    Equals,
)


class TestSSHKeyHandler(MAASServerTestCase):

    def dehydrate_sshkey(self, sshkey):
        data = {
            "id": sshkey.id,
            "user": sshkey.user.id,
            "key": sshkey.key,
            "keysource": sshkey.keysource.id,
            "updated": dehydrate_datetime(sshkey.updated),
            "created": dehydrate_datetime(sshkey.created),
            }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = SSHKeyHandler(user, {})
        sshkey = factory.make_SSHKey(user)
        self.assertEqual(
            self.dehydrate_sshkey(sshkey),
            handler.get({"id": sshkey.id}))

    def test_list(self):
        user = factory.make_User()
        handler = SSHKeyHandler(user, {})
        factory.make_SSHKey(user)
        expected_sshkeys = [
            self.dehydrate_sshkey(sshkey)
            for sshkey in SSHKey.objects.all()
            ]
        self.assertItemsEqual(
            expected_sshkeys,
            handler.list({}))

    def test_create(self):
        user = factory.make_User()
        handler = SSHKeyHandler(user, {})
        key_string = get_data('data/test_rsa0.pub')
        keysource = factory.make_KeySource()
        new_sshkey = handler.create({
            'user': user.id,
            'key': key_string,
            'keysource': keysource.id,
        })
        self.assertThat(new_sshkey, ContainsDict({
            "user": Equals(user.id),
            "key": Equals(key_string),
            "keysource": Equals(keysource.id),
        }))

    def test_delete(self):
        user = factory.make_User()
        sshkey = factory.make_SSHKey(user=user)
        handler = SSHKeyHandler(user, {})
        handler.delete({"id": sshkey.id})
        self.assertIsNone(
            get_one(SSHKey.objects.filter(id=sshkey.id)))
