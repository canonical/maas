#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Unit tests for FIPS SSH key algorithm restrictions on POST /users/me/sshkeys."""

from unittest.mock import AsyncMock, Mock, patch

from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.sshkeys import SshKey
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.sshkeys import SshKeysService

TEST_DSA_KEY = (
    "ssh-dss AAAAB3NzaC1kc3MAAACBANEDqEMh1r8g3Kwxd4a2k8l+SJj"
    "z4sTQCQ2s7gS3eFnHwFKxL0qWrNJt6rO4P9pOiP0Y= test@example.com"
)

TEST_ED25519_KEY = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBEqkw2AgmkjqNjCFuiKXeUgLNmRbgVr8"
    "W2TlAvFybJv ed255@bar"
)

TEST_ECDSA_KEY = (
    "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABB"
    "BC+D8FKi3Z5Y+U0GVa3m8XqGJXGk test@example.com"
)

TEST_RSA_KEY_PREFIX = "ssh-rsa AAAAB3NzaC1yc2EAAAA test@example.com"

BASE_PATH = f"{V3_API_PREFIX}/users/me/sshkeys"

_DUMMY_SSHKEY = SshKey(id=42, key=TEST_ECDSA_KEY, user_id=1)


@pytest.mark.asyncio
class TestSshKeyFIPSValidation:
    @staticmethod
    def _setup_sshkeys_service(services_mock: ServiceCollectionV3) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.create = AsyncMock(return_value=_DUMMY_SSHKEY)

    async def test_dss_key_rejected_in_fips_mode(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """DSA keys rejected with 422 + fips_violation when FIPS is active."""
        self._setup_sshkeys_service(services_mock)

        with patch(
            "maasapiserver.v3.api.public.handlers.sshkeys.is_fips_enabled",
            return_value=True,
        ):
            response = await mocked_api_client_user.post(
                BASE_PATH, json={"key": TEST_DSA_KEY}
            )

        assert response.status_code == 422
        body = response.json()
        assert body.get("fips_violation") is True
        assert "ssh-dss" in body.get("message", "")
        services_mock.sshkeys.create.assert_not_called()

    async def test_ed25519_key_rejected_in_fips_mode(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """Ed25519 keys rejected in FIPS mode."""
        self._setup_sshkeys_service(services_mock)

        with patch(
            "maasapiserver.v3.api.public.handlers.sshkeys.is_fips_enabled",
            return_value=True,
        ):
            response = await mocked_api_client_user.post(
                BASE_PATH, json={"key": TEST_ED25519_KEY}
            )

        assert response.status_code == 422
        body = response.json()
        assert body.get("fips_violation") is True
        services_mock.sshkeys.create.assert_not_called()

    async def test_small_rsa_key_rejected_in_fips_mode(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """RSA keys < 2048 bits rejected in FIPS mode."""
        self._setup_sshkeys_service(services_mock)

        with (
            patch(
                "maasapiserver.v3.api.public.handlers.sshkeys.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "maasapiserver.v3.api.public.handlers.sshkeys"
                ".validate_ssh_key_fips_compliance",
                return_value=(
                    False,
                    "RSA key size 1024 bits is below the FIPS minimum of 2048 bits.",
                    ["RSA ≥ 2048 bits", "ECDSA P-256/384/521"],
                ),
            ),
        ):
            response = await mocked_api_client_user.post(
                BASE_PATH, json={"key": TEST_RSA_KEY_PREFIX}
            )

        assert response.status_code == 422
        body = response.json()
        assert body.get("fips_violation") is True
        assert "2048" in body.get("message", "")
        services_mock.sshkeys.create.assert_not_called()

    async def test_fips_422_response_schema(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """FIPS rejection responses include required schema fields."""
        self._setup_sshkeys_service(services_mock)

        with patch(
            "maasapiserver.v3.api.public.handlers.sshkeys.is_fips_enabled",
            return_value=True,
        ):
            response = await mocked_api_client_user.post(
                BASE_PATH, json={"key": TEST_DSA_KEY}
            )

        assert response.status_code == 422
        body = response.json()
        assert body["fips_violation"] is True
        assert body["code"] == 422
        assert isinstance(body["message"], str) and body["message"]
        assert isinstance(body["allowed_values"], list)

    async def test_ecdsa_p256_key_accepted_in_fips_mode(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """ECDSA P-256 keys accepted in FIPS mode."""
        self._setup_sshkeys_service(services_mock)

        with patch(
            "maasapiserver.v3.api.public.handlers.sshkeys.is_fips_enabled",
            return_value=True,
        ):
            response = await mocked_api_client_user.post(
                BASE_PATH, json={"key": TEST_ECDSA_KEY}
            )

        assert response.status_code == 201
        services_mock.sshkeys.create.assert_called_once()

    async def test_large_rsa_key_accepted_in_fips_mode(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """RSA keys ≥ 2048 bits accepted in FIPS mode."""
        self._setup_sshkeys_service(services_mock)

        with (
            patch(
                "maasapiserver.v3.api.public.handlers.sshkeys.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "maasapiserver.v3.api.public.handlers.sshkeys"
                ".validate_ssh_key_fips_compliance",
                return_value=(True, None, []),
            ),
        ):
            response = await mocked_api_client_user.post(
                BASE_PATH, json={"key": TEST_RSA_KEY_PREFIX}
            )

        assert response.status_code == 201
        services_mock.sshkeys.create.assert_called_once()

    async def test_dss_key_accepted_when_fips_inactive(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """DSA keys accepted when FIPS is inactive."""
        self._setup_sshkeys_service(services_mock)

        with patch(
            "maasapiserver.v3.api.public.handlers.sshkeys.is_fips_enabled",
            return_value=False,
        ):
            response = await mocked_api_client_user.post(
                BASE_PATH, json={"key": TEST_DSA_KEY}
            )

        assert response.status_code == 201
        services_mock.sshkeys.create.assert_called_once()

    async def test_ed25519_key_accepted_when_fips_inactive(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """Ed25519 keys accepted when FIPS is inactive."""
        self._setup_sshkeys_service(services_mock)

        with patch(
            "maasapiserver.v3.api.public.handlers.sshkeys.is_fips_enabled",
            return_value=False,
        ):
            response = await mocked_api_client_user.post(
                BASE_PATH, json={"key": TEST_ED25519_KEY}
            )

        assert response.status_code == 201
        services_mock.sshkeys.create.assert_called_once()
