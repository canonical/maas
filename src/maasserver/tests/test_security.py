# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for MAAS's security module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from binascii import b2a_hex
from datetime import datetime
from os import unlink

from fixtures import EnvironmentVariableFixture
from maasserver import security
from maasserver.models.config import Config
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.djangotestcase import DjangoTransactionTestCase
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.fs import write_text_file
from pytz import UTC
from testtools.matchers import (
    AfterPreprocessing,
    Equals,
    FileContains,
    GreaterThan,
    IsInstance,
    MatchesAll,
    MatchesAny,
)
from twisted.internet import ssl


class TestGetSerial(MAASTestCase):

    def test_that_it_works_eh(self):
        nowish = datetime(2014, 03, 24, 16, 07, tzinfo=UTC)
        security_datetime = self.patch(security, "datetime")
        # Make security.datetime() work like regular datetime.
        security_datetime.side_effect = datetime
        # Make security.datetime.now() return a fixed value.
        security_datetime.now.return_value = nowish
        self.assertEqual(69005220, security.get_serial())


is_valid_region_certificate = MatchesAll(
    IsInstance(ssl.PrivateCertificate),
    AfterPreprocessing(
        lambda cert: cert.getSubject(),
        Equals({"commonName": "MAAS Region"})),
    AfterPreprocessing(
        lambda cert: cert.getPublicKey().original.bits(),
        Equals(2048)),
    AfterPreprocessing(
        lambda cert: cert.privateKey.original.bits(),
        Equals(2048)),
)


class TestCertificateFunctions(MAASServerTestCase):

    def patch_serial(self):
        serial = self.getUniqueInteger()
        self.patch(security, "get_serial").return_value = serial
        return serial

    def test_generate_region_certificate(self):
        serial = self.patch_serial()
        cert = security.generate_region_certificate()
        self.assertThat(cert, is_valid_region_certificate)
        self.assertEqual(serial, cert.serialNumber())

    def test_save_region_certificate(self):
        cert = security.generate_region_certificate()
        security.save_region_certificate(cert)
        self.assertEqual(
            cert.dumpPEM().decode("ascii"),
            Config.objects.get_config("rpc_region_certificate"))

    def test_load_region_certificate(self):
        cert = security.generate_region_certificate()
        Config.objects.set_config(
            "rpc_region_certificate", cert.dumpPEM().decode("ascii"))
        self.assertEqual(cert, security.load_region_certificate())

    def test_load_region_certificate_when_none_exists(self):
        self.assertIsNone(security.load_region_certificate())

    def test_get_region_certificate(self):
        cert = security.generate_region_certificate()
        security.save_region_certificate(cert)
        self.assertEqual(cert, security.get_region_certificate())

    def test_get_region_certificate_when_none_exists(self):
        cert = security.get_region_certificate()
        self.assertThat(cert, is_valid_region_certificate)
        self.assertEqual(cert, security.load_region_certificate())


is_valid_secret = MatchesAll(
    IsInstance(bytes), AfterPreprocessing(
        len, MatchesAny(Equals(16), GreaterThan(16))))


class TestGetSharedSecret(DjangoTransactionTestCase):

    def setUp(self):
        super(TestGetSharedSecret, self).setUp()
        self.useFixture(EnvironmentVariableFixture(
            "MAAS_ROOT", self.make_dir()))

    def test__generates_new_secret_when_none_exists(self):
        secret = security.get_shared_secret()
        self.assertThat(secret, is_valid_secret)

    def test__same_secret_is_returned_on_subsequent_calls(self):
        self.assertEqual(
            security.get_shared_secret(),
            security.get_shared_secret())

    def test__uses_database_secret_when_none_on_fs(self):
        secret_before = security.get_shared_secret()
        unlink(security.get_shared_secret_filesystem_path())
        secret_after = security.get_shared_secret()
        self.assertEqual(secret_before, secret_after)
        # The secret found in the database is written to the filesystem.
        self.assertThat(
            security.get_shared_secret_filesystem_path(),
            FileContains(b2a_hex(secret_after)))

    def test__uses_filesystem_secret_when_none_in_database(self):
        secret_before = security.get_shared_secret()
        Config.objects.set_config("rpc_shared_secret", None)
        secret_after = security.get_shared_secret()
        self.assertEqual(secret_before, secret_after)
        # The secret found on the filesystem is saved in the database.
        self.assertEqual(
            b2a_hex(secret_after),
            Config.objects.get_config("rpc_shared_secret"))

    def test__errors_when_database_value_cannot_be_decoded(self):
        security.get_shared_secret()  # Ensure that the directory exists.
        Config.objects.set_config("rpc_shared_secret", "_")
        self.assertRaises(TypeError, security.get_shared_secret)

    def test__errors_when_database_and_filesystem_values_differ(self):
        security.get_shared_secret()  # Ensure that the directory exists.
        Config.objects.set_config("rpc_shared_secret", "666f6f")
        write_text_file(
            security.get_shared_secret_filesystem_path(), "626172")
        self.assertRaises(AssertionError, security.get_shared_secret)

    def test__deals_fine_with_whitespace_in_database_value(self):
        Config.objects.set_config("rpc_shared_secret", " 666f6f\n")
        # Ordinarily we would need to commit now, because get_shared_secret()
        # runs in a separate thread. However, Django thinks that transaction
        # management means AUTOCOMMIT, which spares us this diabolical chore.
        # This is not unique to this test method; it comes from using Django's
        # DjangoTransactionTestCase, which also has a misleading name.
        self.assertEqual(b"foo", security.get_shared_secret())
