# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock, patch

from cryptography.hazmat.primitives.asymmetric.dsa import DSAPublicKey
import pytest

from maasservicelayer.builders.sslkeys import SSLKeyBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.sslkeys import SSLKeysRepository
from maasservicelayer.exceptions.catalog import FIPSViolationException
from maasservicelayer.services.sslkey import SSLKeysService


@pytest.mark.asyncio
class TestSSLKeysServiceFIPSValidation:
    @pytest.fixture(autouse=True)
    def enable_fips(self, monkeypatch):
        monkeypatch.setattr(
            "maasservicelayer.services.sslkey.is_fips_enabled",
            lambda: True,
        )

    async def test_fips_rejects_dsa_cert(self) -> None:
        repository = Mock(SSLKeysRepository)
        repository.exists.return_value = False
        service = SSLKeysService(
            context=Context(), sslkey_repository=repository
        )
        mock_cert = Mock()
        mock_dsa_key = Mock(spec=DSAPublicKey)
        mock_cert.public_key.return_value = mock_dsa_key
        mock_cert.signature_algorithm_oid = Mock()
        mock_cert.signature_algorithm_oid._name = "dsaWithSHA1"
        with patch(
            "cryptography.x509.load_pem_x509_certificate",
            return_value=mock_cert,
        ):
            with pytest.raises(FIPSViolationException):
                await service.pre_create_hook(
                    SSLKeyBuilder(
                        key="-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----",
                        user_id=1,
                    )
                )

    async def test_fips_rejects_sha1_signed_cert(self) -> None:
        repository = Mock(SSLKeysRepository)
        repository.exists.return_value = False
        service = SSLKeysService(
            context=Context(), sslkey_repository=repository
        )

        mock_cert = Mock()
        mock_rsa_key = Mock()
        mock_rsa_key.__class__.__name__ = "RSAPublicKey"
        mock_cert.public_key.return_value = mock_rsa_key
        mock_cert.signature_algorithm_oid = Mock()
        mock_cert.signature_algorithm_oid._name = "sha1WithRSAEncryption"

        # Need to match one of the OID constants
        from cryptography import x509

        mock_cert.signature_algorithm_oid = (
            x509.oid.SignatureAlgorithmOID.RSA_WITH_SHA1
        )

        with patch(
            "cryptography.x509.load_pem_x509_certificate",
            return_value=mock_cert,
        ):
            with pytest.raises(FIPSViolationException):
                await service.pre_create_hook(
                    SSLKeyBuilder(key="dummy_pem", user_id=1)
                )

    async def test_fips_allows_compliant_cert(self) -> None:
        repository = Mock(SSLKeysRepository)
        repository.exists.return_value = False
        service = SSLKeysService(
            context=Context(), sslkey_repository=repository
        )

        mock_cert = Mock()
        mock_rsa_key = Mock()
        mock_rsa_key.__class__.__name__ = "RSAPublicKey"
        mock_rsa_key.key_size = 4096
        mock_cert.public_key.return_value = mock_rsa_key
        mock_cert.signature_algorithm_oid = Mock()
        mock_cert.signature_algorithm_oid._name = "sha256WithRSAEncryption"

        # Match a compliant OID
        from cryptography import x509

        mock_cert.signature_algorithm_oid = (
            x509.oid.SignatureAlgorithmOID.RSA_WITH_SHA256
        )

        with patch(
            "cryptography.x509.load_pem_x509_certificate",
            return_value=mock_cert,
        ):
            await service.pre_create_hook(
                SSLKeyBuilder(key="dummy_pem", user_id=1)
            )


@pytest.mark.asyncio
class TestSSLKeysServiceNonFIPSValidation:
    async def test_non_fips_allows_small_rsa_cert(self) -> None:
        repository = Mock(SSLKeysRepository)
        repository.exists.return_value = False
        service = SSLKeysService(
            context=Context(), sslkey_repository=repository
        )

        mock_cert = Mock()
        mock_rsa_key = Mock()
        mock_rsa_key.__class__.__name__ = "RSAPublicKey"
        mock_rsa_key.key_size = 1024
        mock_cert.public_key.return_value = mock_rsa_key
        mock_cert.signature_algorithm_oid = Mock()
        mock_cert.signature_algorithm_oid._name = "sha256WithRSAEncryption"

        from cryptography import x509

        mock_cert.signature_algorithm_oid = (
            x509.oid.SignatureAlgorithmOID.RSA_WITH_SHA256
        )

        with (
            patch(
                "cryptography.x509.load_pem_x509_certificate",
                return_value=mock_cert,
            ),
            patch(
                "maasservicelayer.services.sslkey.is_fips_enabled",
                return_value=False,
            ),
        ):
            await service.pre_create_hook(
                SSLKeyBuilder(key="dummy_pem", user_id=1)
            )
