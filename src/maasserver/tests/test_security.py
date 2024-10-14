# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import binascii
from datetime import datetime

from pytz import UTC

from maasserver import security
from maasserver.secrets import SecretManager
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maastesting.testcase import MAASTestCase


class TestGetSerial(MAASTestCase):
    def test_serial_generated(self):
        nowish = datetime(2014, 0o3, 24, 16, 0o7, tzinfo=UTC)
        security_datetime = self.patch(security, "datetime")
        # Make security.datetime() work like regular datetime.
        security_datetime.side_effect = datetime
        # Make security.timezone.now() return a fixed value.
        security_datetime.now.return_value = nowish
        self.assertEqual(69005220, security.get_serial())


class TestGetSharedSecret(MAASTransactionServerTestCase):
    def test_generates_new_secret_when_unset(self):
        secret = security.get_shared_secret()
        self.assertIsInstance(secret, bytes)
        self.assertGreaterEqual(len(secret), 16)

    def test_same_secret_is_returned_on_subsequent_calls(self):
        self.assertEqual(
            security.get_shared_secret(), security.get_shared_secret()
        )

    def test_errors_when_database_value_cannot_be_decoded(self):
        SecretManager().set_simple_secret("rpc-shared", "_")
        self.assertRaises(binascii.Error, security.get_shared_secret)
