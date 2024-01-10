# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.sslkey`"""


from maasserver.models.sslkey import SSLKey
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one
from maasserver.websockets.base import HandlerDoesNotExistError
from maasserver.websockets.handlers.sslkey import SSLKeyHandler
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime


class TestSSLKeyHandler(MAASServerTestCase):
    def dehydrate_sslkey(self, sslkey):
        return {
            "id": sslkey.id,
            "display": sslkey.display_html(),
            "user": sslkey.user.id,
            "key": sslkey.key,
            "updated": dehydrate_datetime(sslkey.updated),
            "created": dehydrate_datetime(sslkey.created),
        }

    def test_get(self):
        user = factory.make_User()
        handler = SSLKeyHandler(user, {}, None)
        sslkey = factory.make_SSLKey(user)
        self.assertEqual(
            self.dehydrate_sslkey(sslkey), handler.get({"id": sslkey.id})
        )

    def test_get_doesnt_work_if_not_owned(self):
        user = factory.make_User()
        handler = SSLKeyHandler(user, {}, None)
        not_owned_sslkey = factory.make_SSLKey(factory.make_User())
        self.assertRaises(
            HandlerDoesNotExistError, handler.get, {"id": not_owned_sslkey.id}
        )

    def test_list(self):
        user = factory.make_User()
        handler = SSLKeyHandler(user, {}, None)
        factory.make_SSLKey(user)
        expected_sslkeys = [
            self.dehydrate_sslkey(sslkey) for sslkey in SSLKey.objects.all()
        ]
        self.assertCountEqual(expected_sslkeys, handler.list({}))

    def test_create(self):
        user = factory.make_User()
        handler = SSLKeyHandler(user, {}, None)
        key_string = get_data("data/test_x509_0.pem")
        new_sslkey = handler.create({"key": key_string})
        self.assertEqual(new_sslkey.get("user"), user.id)
        self.assertEqual(new_sslkey.get("key"), key_string)

    def test_delete(self):
        user = factory.make_User()
        sslkey = factory.make_SSLKey(user=user)
        handler = SSLKeyHandler(user, {}, None)
        handler.delete({"id": sslkey.id})
        self.assertIsNone(get_one(SSLKey.objects.filter(id=sslkey.id)))
