# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from OpenSSL import crypto as ossl_crypto

from maasserver.models import SSLKey, sslkey
from maasserver.models.sslkey import validate_ssl_key
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestSSLKeyValidator(MAASServerTestCase):
    def test_validates_x509_public_key(self):
        key_string = get_data("data/test_x509_0.pem")
        validate_ssl_key(key_string)
        # No ValidationError.

    def test_does_not_validate_random_data(self):
        key_string = factory.make_string()
        self.assertRaises(ValidationError, validate_ssl_key, key_string)


def _make_ssl_cert(key_type="rsa", key_size=2048, hash_alg="sha256"):
    """Generate a self-signed PEM certificate for testing.

    :param key_type: "rsa" or "dsa"
    :param key_size: key size in bits
    :param hash_alg: signature hash algorithm name (e.g. "sha1", "sha256")
    :return: PEM-encoded certificate string
    """
    k = ossl_crypto.PKey()
    if key_type == "dsa":
        k.generate_key(ossl_crypto.TYPE_DSA, key_size)
    else:
        k.generate_key(ossl_crypto.TYPE_RSA, key_size)
    cert = ossl_crypto.X509()
    cert.get_subject().CN = "test"
    cert.set_serial_number(1)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, hash_alg)
    return ossl_crypto.dump_certificate(
        ossl_crypto.FILETYPE_PEM, cert
    ).decode()


class TestSSLKeyValidatorFIPS(MAASServerTestCase):
    """Tests for FIPS-conditional validation in validate_ssl_key."""

    def test_fips_rejects_sha1_cert(self):
        pem = _make_ssl_cert(key_type="rsa", key_size=2048, hash_alg="sha1")
        self.patch(sslkey, "is_fips_enabled").return_value = True
        error = self.assertRaises(ValidationError, validate_ssl_key, pem)
        self.assertEqual("fips_violation", error.code)

    def test_fips_rejects_dsa_cert(self):
        pem = _make_ssl_cert(key_type="dsa", key_size=2048, hash_alg="sha256")
        self.patch(sslkey, "is_fips_enabled").return_value = True
        error = self.assertRaises(ValidationError, validate_ssl_key, pem)
        self.assertEqual("fips_violation", error.code)

    def test_fips_rejects_small_rsa_cert(self):
        pem = _make_ssl_cert(key_type="rsa", key_size=1024, hash_alg="sha256")
        self.patch(sslkey, "is_fips_enabled").return_value = True
        error = self.assertRaises(ValidationError, validate_ssl_key, pem)
        self.assertEqual("fips_violation", error.code)

    def test_fips_accepts_sha256_rsa2048_cert(self):
        pem = _make_ssl_cert(key_type="rsa", key_size=2048, hash_alg="sha256")
        self.patch(sslkey, "is_fips_enabled").return_value = True
        # No exception should be raised.
        validate_ssl_key(pem)

    def test_no_fips_check_when_disabled(self):
        pem = _make_ssl_cert(key_type="rsa", key_size=2048, hash_alg="sha1")
        self.patch(sslkey, "is_fips_enabled").return_value = False
        # SHA-1 cert accepted when FIPS is disabled.
        validate_ssl_key(pem)


class TestSSLKey(MAASServerTestCase):
    def test_sslkey_validation_with_valid_key(self):
        key_string = get_data("data/test_x509_0.pem")
        user = factory.make_User()
        key = SSLKey(key=key_string, user=user)
        key.full_clean()
        # No ValidationError.

    def test_sslkey_validation_fails_if_key_is_invalid(self):
        key_string = factory.make_string()
        user = factory.make_User()
        key = SSLKey(key=key_string, user=user)
        self.assertRaises(ValidationError, key.full_clean)

    def test_sslkey_user_and_key_unique_together(self):
        key_string = get_data("data/test_x509_0.pem")
        user = factory.make_User()
        key = SSLKey(key=key_string, user=user)
        key.save()
        key2 = SSLKey(key=key_string, user=user)
        self.assertRaises(ValidationError, key2.full_clean)

    def test_sslkey_user_and_key_unique_together_db_level(self):
        # Even if we hack our way around model-level checks, uniqueness
        # of the user/key combination is enforced at the database level.
        key_string = get_data("data/test_x509_0.pem")
        user = factory.make_User()
        existing_key = SSLKey(key=key_string, user=user)
        existing_key.save()
        # The trick to hack around the model-level checks: create a
        # duplicate key for another user, then attach it to the same
        # user as the existing key by updating it directly in the
        # database.
        redundant_key = SSLKey(key=key_string, user=factory.make_User())
        redundant_key.save()
        self.assertRaises(
            IntegrityError,
            SSLKey.objects.filter(id=redundant_key.id).update,
            user=user,
        )

    def test_sslkey_same_key_can_be_used_by_different_users(self):
        key_string = get_data("data/test_x509_0.pem")
        user = factory.make_User()
        key = SSLKey(key=key_string, user=user)
        key.save()
        user2 = factory.make_User()
        key2 = SSLKey(key=key_string, user=user2)
        key2.full_clean()
        # No ValidationError.


class TestSSLKeyManager(MAASServerTestCase):
    def test_get_keys_for_user_no_keys(self):
        user = factory.make_User()
        keys = SSLKey.objects.get_keys_for_user(user)
        self.assertCountEqual([], keys)

    def test_get_keys_for_user_with_keys(self):
        user1, created_keys = factory.make_user_with_ssl_keys(
            n_keys=3, username="user1"
        )
        # user2
        factory.make_user_with_ssl_keys(n_keys=2)
        keys = SSLKey.objects.get_keys_for_user(user1)
        self.assertCountEqual([key.key for key in created_keys], keys)
