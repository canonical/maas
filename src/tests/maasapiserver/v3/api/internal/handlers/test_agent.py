# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from typing import Awaitable, Callable
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from httpx import AsyncClient
from OpenSSL import crypto
import pytest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from maasapiserver.v3.constants import V3_INTERNAL_API_PREFIX
from maasservicelayer.exceptions.constants import INVALID_TOKEN_VIOLATION_TYPE
from maasservicelayer.models.agents import Agent
from maasservicelayer.models.bootstraptokens import BootstrapToken
from maasservicelayer.models.racks import Rack
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.agents import AgentsService
from maasservicelayer.services.bootstraptoken import BootstrapTokensService
from maasservicelayer.services.racks import RacksService
from maasservicelayer.services.secrets import SecretsService
from maasservicelayer.utils.date import utcnow
from provisioningserver.certificates import Certificate

"""
Instructions to generate a Certificate Signing Request (CSR) with certain
Common Name (CN)

# generate a private key
$ openssl genrsa -out private.key 1024

# generate a CSR using that private key
$ openssl req -new -key private.key -out request.csr -subj "/CN=01f09d32-f508-6064-bd1c-c025a58dd068"

# now we have private.key and request.csr
# - inspect the raw CSR
$ cat request.csr
# - inspect the decode CSR and verify CN
$ openssl req -in request.csr -noout -text
"""
CSR = "\n".join(
    [
        "-----BEGIN CERTIFICATE REQUEST-----",
        "MIIBbjCB2AIBADAvMS0wKwYDVQQDDCQwMWYwOWQzMi1mNTA4LTYwNjQtYmQxYy1j",
        "MDI1YTU4ZGQwNjgwgZ8wDQYJKoZIhvcNAQEBBQADgY0AMIGJAoGBAKuwhG8GrttS",
        "Jn8IFtagVM9b0e6OIor+mt00hSz9sf/U+q03QpDXVhkumU4EoJlU8EFqCANMClwX",
        "pmEI4xmRjr8DUgIP7zuTu8wacaQCoHMWvxg8sTb66G3FaD0tDqo4S6/31Ea4LDZ4",
        "ycdn2/cT9BLCdNazt/NxAdWAeYtB4ASHAgMBAAGgADANBgkqhkiG9w0BAQsFAAOB",
        "gQB06a8a64WR3qZL1j1Q1jWVK1/d189s0jY0zW6DUlNdaPBSMD67asbqDB6uCacD",
        "on1EEkebWMQG3uLsXE37/t9a7rRvRIAqD+L45ukfbzgjZ1LQmDYSWLhWuTzgfm69",
        "KvJsHcrkPdJ2ETV9zhvIqBWasyhRYzjn0bOQ/jIuiMItyw==",
        "-----END CERTIFICATE REQUEST-----",
    ]
)
UUID = "01f09d32-f508-6064-bd1c-c025a58dd068"


class InjectFakeTLSCN(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.scope.setdefault("extensions", {})
        request.scope["extensions"]["tls"] = {
            "CN": "01f09d32-f508-6064-bd1c-c025a58dd068"
        }
        return await call_next(request)


@pytest.mark.asyncio
class TestAgentsApi:
    BASE_PATH = f"{V3_INTERNAL_API_PREFIX}/agents"

    @pytest.fixture
    def internal_api_headers(self) -> dict:
        """Returns headers required for internal API requests"""
        return {"client-cert-cn": "test-client"}

    @patch(
        "maasapiserver.v3.api.internal.handlers.agent.sign_certificate_request"
    )
    @patch(
        "maasapiserver.v3.api.internal.handlers.agent.fetch_maas_ca_cert",
        new_callable=AsyncMock,
    )
    @patch(
        "maasapiserver.v3.api.internal.handlers.agent.crypto.dump_certificate",
    )
    async def test_agent_enrollment_success(
        self,
        mock_dump_certificate,
        mock_fetch_maas_ca_cert,
        mock_sign_certificate_request,
        services_mock: ServiceCollectionV3,
        mocked_internal_api_client: AsyncClient,
        internal_app_with_mocked_services: FastAPI,
        internal_api_headers: dict,
    ) -> None:
        internal_app_with_mocked_services.add_middleware(InjectFakeTLSCN)
        mock_dump_certificate.side_effect = [
            b"signed_cert_pem_bytes",
            b"ca_cert_pem_bytes",
        ]

        mock_x509name = Mock(crypto.X509Name)
        mock_x509name.CN = UUID
        mock_x509 = Mock(crypto.X509)
        mock_x509.get_subject.return_value = mock_x509name
        mock_certificate = Mock(Certificate)
        mock_certificate.cert = mock_x509
        mock_sign_certificate_request.return_value = mock_certificate

        mock_ca_certificate = Mock(Certificate)
        mock_ca_certificate.cert = Mock(crypto.X509)
        mock_fetch_maas_ca_cert.return_value = mock_ca_certificate

        services_mock.bootstraptokens = Mock(BootstrapTokensService)
        mock_token = BootstrapToken(
            id=1,
            secret="test-secret",
            rack_id=1,
            expires_at=utcnow() + timedelta(minutes=5),
        )
        services_mock.bootstraptokens.get_one.return_value = mock_token
        services_mock.racks = Mock(RacksService)
        mock_rack = Rack(id=1, name="test-rack")
        services_mock.racks.get_one.return_value = mock_rack
        services_mock.secrets = Mock(SecretsService)
        mock_ca_secret = {
            "key": "mock-key",
            "cert": "mock-cert",
            "cacert": "mock-cacert",
        }
        services_mock.secrets.get_composite_secret.return_value = (
            mock_ca_secret
        )
        services_mock.agents = Mock(AgentsService)
        mock_agent = Agent(id=1, uuid=UUID, rack_id=1)
        services_mock.agents.create.return_value = mock_agent

        request_data = {"secret": "test-secret", "csr": CSR}
        response = await mocked_internal_api_client.post(
            f"{self.BASE_PATH}:enroll",
            json=request_data,
        )
        assert response.status_code == 201
        response_json = response.json()
        assert "certificate" in response_json
        assert "ca" in response_json
        assert response_json["certificate"] == "signed_cert_pem_bytes"
        assert response_json["ca"] == "ca_cert_pem_bytes"
        assert "ETag" in response.headers

        assert mock_dump_certificate.call_count == 2
        services_mock.bootstraptokens.delete_one.assert_called_once()

    async def test_agent_enrollment_failed_with_not_found_secret(
        self,
        services_mock: ServiceCollectionV3,
        mocked_internal_api_client: AsyncClient,
        internal_api_headers: dict,
    ) -> None:
        services_mock.bootstraptokens = Mock(BootstrapTokensService)
        services_mock.bootstraptokens.get_one.return_value = None

        request_data = {"secret": "invalid-secret", "csr": CSR}

        response = await mocked_internal_api_client.post(
            f"{self.BASE_PATH}:enroll",
            json=request_data,
            headers=internal_api_headers,
        )
        assert response.status_code == 401
        response_json = response.json()
        assert (
            response_json["details"][0]["type"] == INVALID_TOKEN_VIOLATION_TYPE
        )
        assert (
            response_json["details"][0]["message"]
            == "Bootstrap token invalid or expired."
        )

    async def test_agent_enrollment_with_expired_secret(
        self,
        services_mock: ServiceCollectionV3,
        mocked_internal_api_client: AsyncClient,
        internal_api_headers: dict,
    ) -> None:
        services_mock.bootstraptokens = Mock(BootstrapTokensService)
        mock_token = BootstrapToken(
            id=1,
            secret="test-secret",
            rack_id=1,
            expires_at=utcnow()
            - timedelta(minutes=5),  # expired 5 minutes ago
        )
        services_mock.bootstraptokens.get_one.return_value = mock_token

        request_data = {"secret": "test-secret", "csr": CSR}

        response = await mocked_internal_api_client.post(
            f"{self.BASE_PATH}:enroll",
            json=request_data,
            headers=internal_api_headers,
        )
        assert response.status_code == 401
        response_json = response.json()
        assert (
            response_json["details"][0]["type"] == INVALID_TOKEN_VIOLATION_TYPE
        )
        assert (
            response_json["details"][0]["message"]
            == "Bootstrap token invalid or expired."
        )
