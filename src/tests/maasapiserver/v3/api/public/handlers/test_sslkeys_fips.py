#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Unit tests for FIPS TLS certificate restrictions on POST /users/me/sslkeys."""

from unittest.mock import AsyncMock, Mock, patch

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.requests.sslkeys import SSLKeyRequest
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.sslkeys import SSLKey
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.sslkey import SSLKeysService
from maasservicelayer.utils.date import utcnow
from tests.fixtures import get_test_data_file

BASE_PATH = f"{V3_API_PREFIX}/users/me/sslkeys"

_FIPS_COMPLIANT_PEM = get_test_data_file("test_x509_0.pem")

_DUMMY_SSLKEY = SSLKey(
    id=1,
    key=_FIPS_COMPLIANT_PEM,
    created=utcnow(),
    updated=utcnow(),
    user_id=1,
)


@pytest.mark.asyncio
class TestSSLKeyFIPSValidation:
    @staticmethod
    def _setup_sslkeys_service(services_mock: ServiceCollectionV3) -> None:
        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.create = AsyncMock(return_value=_DUMMY_SSLKEY)

    async def test_sha1_cert_rejected_in_fips_mode(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """SHA-1 certificates rejected in FIPS mode."""
        self._setup_sslkeys_service(services_mock)

        with (
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys"
                ".validate_ssl_cert_fips_compliance",
                return_value=(
                    False,
                    "Certificate signature uses 'sha1' which is not permitted"
                    " in FIPS mode. Use SHA-256 or stronger.",
                    [
                        "RSA ≥ 2048 bits with SHA-256 or stronger",
                        "ECDSA P-256/384/521 with SHA-256 or stronger",
                    ],
                ),
            ),
        ):
            create_request = SSLKeyRequest(key=_FIPS_COMPLIANT_PEM)
            response = await mocked_api_client_user.post(
                BASE_PATH,
                json=jsonable_encoder(create_request),
            )

        assert response.status_code == 422
        body = response.json()
        assert body.get("fips_violation") is True
        assert "sha1" in body.get("message", "").lower()
        services_mock.sslkeys.create.assert_not_called()

    async def test_md5_cert_rejected_in_fips_mode(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """MD5 certificates rejected in FIPS mode."""
        self._setup_sslkeys_service(services_mock)

        with (
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys"
                ".validate_ssl_cert_fips_compliance",
                return_value=(
                    False,
                    "Certificate signature uses 'md5' which is not permitted"
                    " in FIPS mode. Use SHA-256 or stronger.",
                    [
                        "RSA ≥ 2048 bits with SHA-256 or stronger",
                        "ECDSA P-256/384/521 with SHA-256 or stronger",
                    ],
                ),
            ),
        ):
            create_request = SSLKeyRequest(key=_FIPS_COMPLIANT_PEM)
            response = await mocked_api_client_user.post(
                BASE_PATH,
                json=jsonable_encoder(create_request),
            )

        assert response.status_code == 422
        body = response.json()
        assert body.get("fips_violation") is True
        assert "md5" in body.get("message", "").lower()
        services_mock.sslkeys.create.assert_not_called()

    async def test_small_rsa_cert_rejected_in_fips_mode(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """RSA keys < 2048 bits rejected in FIPS mode."""
        self._setup_sslkeys_service(services_mock)

        with (
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys"
                ".validate_ssl_cert_fips_compliance",
                return_value=(
                    False,
                    "RSA key size 1024 bits is below the FIPS minimum of 2048"
                    " bits.",
                    [
                        "RSA ≥ 2048 bits with SHA-256 or stronger",
                        "ECDSA P-256/384/521 with SHA-256 or stronger",
                    ],
                ),
            ),
        ):
            create_request = SSLKeyRequest(key=_FIPS_COMPLIANT_PEM)
            response = await mocked_api_client_user.post(
                BASE_PATH,
                json=jsonable_encoder(create_request),
            )

        assert response.status_code == 422
        body = response.json()
        assert body.get("fips_violation") is True
        assert "2048" in body.get("message", "")
        services_mock.sslkeys.create.assert_not_called()

    async def test_dsa_cert_rejected_in_fips_mode(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """DSA certificates rejected in FIPS mode."""
        self._setup_sslkeys_service(services_mock)

        with (
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys"
                ".validate_ssl_cert_fips_compliance",
                return_value=(
                    False,
                    "DSA public keys are not FIPS 140-3 approved.",
                    [
                        "RSA ≥ 2048 bits with SHA-256 or stronger",
                        "ECDSA P-256/384/521 with SHA-256 or stronger",
                    ],
                ),
            ),
        ):
            create_request = SSLKeyRequest(key=_FIPS_COMPLIANT_PEM)
            response = await mocked_api_client_user.post(
                BASE_PATH,
                json=jsonable_encoder(create_request),
            )

        assert response.status_code == 422
        body = response.json()
        assert body.get("fips_violation") is True
        assert "DSA" in body.get("message", "")
        services_mock.sslkeys.create.assert_not_called()

    async def test_fips_422_response_schema(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """FIPS rejection response includes required fields."""
        self._setup_sslkeys_service(services_mock)

        with (
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys"
                ".validate_ssl_cert_fips_compliance",
                return_value=(
                    False,
                    "Certificate signature uses 'sha1' which is not permitted.",
                    ["RSA ≥ 2048 bits with SHA-256", "ECDSA P-256/384/521"],
                ),
            ),
        ):
            create_request = SSLKeyRequest(key=_FIPS_COMPLIANT_PEM)
            response = await mocked_api_client_user.post(
                BASE_PATH,
                json=jsonable_encoder(create_request),
            )

        assert response.status_code == 422
        body = response.json()
        assert body["fips_violation"] is True
        assert body["code"] == 422
        assert isinstance(body["message"], str) and body["message"]
        assert isinstance(body["allowed_values"], list)

    async def test_sha256_rsa2048_cert_accepted_in_fips_mode(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """SHA-256/RSA-2048 certificates accepted in FIPS mode."""
        self._setup_sslkeys_service(services_mock)

        with patch(
            "maasapiserver.v3.api.public.handlers.sslkeys.is_fips_enabled",
            return_value=True,
        ):
            create_request = SSLKeyRequest(key=_FIPS_COMPLIANT_PEM)
            response = await mocked_api_client_user.post(
                BASE_PATH,
                json=jsonable_encoder(create_request),
            )

        assert response.status_code == 201
        services_mock.sslkeys.create.assert_called_once()

    async def test_sha1_cert_accepted_when_fips_inactive(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """SHA-1 certificates accepted when FIPS is inactive."""
        self._setup_sslkeys_service(services_mock)

        with patch(
            "maasapiserver.v3.api.public.handlers.sslkeys.is_fips_enabled",
            return_value=False,
        ):
            create_request = SSLKeyRequest(key=_FIPS_COMPLIANT_PEM)
            response = await mocked_api_client_user.post(
                BASE_PATH,
                json=jsonable_encoder(create_request),
            )

        assert response.status_code == 201
        services_mock.sslkeys.create.assert_called_once()

    async def test_fips_validation_not_called_when_fips_inactive(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """FIPS validation not called when FIPS is inactive."""
        self._setup_sslkeys_service(services_mock)

        with (
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys.is_fips_enabled",
                return_value=False,
            ),
            patch(
                "maasapiserver.v3.api.public.handlers.sslkeys"
                ".validate_ssl_cert_fips_compliance",
            ) as mock_validate,
        ):
            create_request = SSLKeyRequest(key=_FIPS_COMPLIANT_PEM)
            await mocked_api_client_user.post(
                BASE_PATH,
                json=jsonable_encoder(create_request),
            )

        mock_validate.assert_not_called()
