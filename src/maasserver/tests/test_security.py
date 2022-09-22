# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for MAAS's security module."""


import binascii
from binascii import b2a_hex
from datetime import datetime
from pathlib import Path

from pytz import UTC
from testtools.matchers import (
    AfterPreprocessing,
    Equals,
    IsInstance,
    MatchesAll,
)
from twisted.internet import ssl

from maasserver import security
from maasserver.models.config import Config
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.env import MAAS_SHARED_SECRET


class TestGetSerial(MAASTestCase):
    def test_that_it_works_eh(self):
        nowish = datetime(2014, 0o3, 24, 16, 0o7, tzinfo=UTC)
        security_datetime = self.patch(security, "datetime")
        # Make security.datetime() work like regular datetime.
        security_datetime.side_effect = datetime
        # Make security.datetime.now() return a fixed value.
        security_datetime.now.return_value = nowish
        self.assertEqual(69005220, security.get_serial())


is_valid_region_certificate = MatchesAll(
    IsInstance(ssl.PrivateCertificate),
    AfterPreprocessing(
        lambda cert: cert.getSubject(), Equals({"commonName": b"MAAS Region"})
    ),
    AfterPreprocessing(
        lambda cert: cert.getPublicKey().original.bits(), Equals(2048)
    ),
    AfterPreprocessing(
        lambda cert: cert.privateKey.original.bits(), Equals(2048)
    ),
)


class TestGetSharedSecret(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        Config.objects.set_config("rpc_shared_secret", None)
        tempdir = Path(self.useFixture(TempDirectory()).path)
        MAAS_SHARED_SECRET.clear_cached()
        self.patch(MAAS_SHARED_SECRET, "path", tempdir / "secret")

    def test_generates_new_secret_when_none_exists(self):
        secret = security.get_shared_secret()
        self.assertIsInstance(secret, bytes)
        self.assertGreaterEqual(len(secret), 16)

    def test_same_secret_is_returned_on_subsequent_calls(self):
        self.assertEqual(
            security.get_shared_secret(), security.get_shared_secret()
        )

    def test_uses_database_secret_when_none_on_fs(self):
        secret_before = security.get_shared_secret()
        MAAS_SHARED_SECRET.path.unlink(missing_ok=True)
        secret_after = security.get_shared_secret()
        self.assertEqual(secret_before, secret_after)
        # The secret found in the database is written to the filesystem.
        self.assertEqual(
            MAAS_SHARED_SECRET.get(), b2a_hex(secret_after).decode("ascii")
        )

    def test_uses_filesystem_secret_when_none_in_database(self):
        secret_before = security.get_shared_secret()
        Config.objects.set_config("rpc_shared_secret", None)
        secret_after = security.get_shared_secret()
        self.assertEqual(secret_before, secret_after)
        # The secret found on the filesystem is saved in the database.
        self.assertEqual(
            b2a_hex(secret_after).decode("ascii"),
            Config.objects.get_config("rpc_shared_secret"),
        )

    def test_errors_when_database_value_cannot_be_decoded(self):
        Config.objects.set_config("rpc_shared_secret", "_")
        self.assertRaises(binascii.Error, security.get_shared_secret)

    def test_errors_when_database_and_filesystem_values_differ(self):
        Config.objects.set_config("rpc_shared_secret", "666f6f")
        MAAS_SHARED_SECRET.set("626172")
        self.assertRaises(AssertionError, security.get_shared_secret)

    def test_deals_fine_with_whitespace_in_database_value(self):
        Config.objects.set_config("rpc_shared_secret", " 666f6f\n")
        # Ordinarily we would need to commit now, because get_shared_secret()
        # runs in a separate thread. However, Django thinks that transaction
        # management means AUTOCOMMIT, which spares us this diabolical chore.
        # This is not unique to this test method; it comes from using Django's
        # MAASTransactionServerTestCase, which also has a misleading name.
        self.assertEqual(b"foo", security.get_shared_secret())
