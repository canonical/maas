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

from datetime import datetime

from maasserver import security
from maasserver.models.config import Config
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.testcase import MAASTestCase
from pytz import UTC
from testtools.matchers import (
    AfterPreprocessing,
    Equals,
    IsInstance,
    MatchesAll,
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
