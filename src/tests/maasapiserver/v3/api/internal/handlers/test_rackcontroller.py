# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
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
from maascommon.logging.security import (
    AUTHN_TOKEN_REUSED,
    BOOTSTRAP_TOKEN,
    hash_token_for_logging,
    SECURITY,
)
from maasservicelayer.exceptions.catalog import (
    NotFoundException,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_TOKEN_VIOLATION_TYPE,
    PRECONDITION_FAILED,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.bootstraptokens import BootstrapToken
from maasservicelayer.models.dhcp import (
    DHCPDataForRackController,
    HostReservationData,
    InterfaceData,
    IPRangeData,
    KeaHAConfig,
    SubnetData,
    VlanData,
)
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.rackcontrollers import RackController
from maasservicelayer.models.racks import Rack
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.dhcp import DHCPService
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

DHCP_DATA = DHCPDataForRackController(
    vlans=[VlanData(id=1, vid=0, relayed_vlan_id=None, mtu=1500)],
    subnets=[
        SubnetData(
            id=1,
            rack_system_id="rack-1",
            secondary_rack_system_id="rack-2",
            ip_version=4,
            cidr="10.0.0.0/24",
            gateway_ip="10.0.0.1",
            dns_servers=["10.0.0.2"],
            allow_dns=True,
            vlan_id=1,
            vlan_mtu=1500,
            mask="255.255.255.0",
            broadcast_ip="10.0.0.255",
            domain_name="maas",
            search_list=["maas"],
            ntp_servers=["10.0.0.3"],
            next_server="10.0.0.2",
            pools=[
                IPRangeData(
                    id=1,
                    subnet_id=1,
                    dynamic=True,
                    start_ip="10.0.0.100",
                    end_ip="10.0.0.200",
                )
            ],
            host_reservations=[
                HostReservationData(
                    ip="10.0.0.10",
                    mac_address="00:11:22:33:44:55",
                    hostname="machine-1",
                )
            ],
        )
    ],
    ipranges=[
        IPRangeData(
            id=1,
            subnet_id=1,
            dynamic=True,
            start_ip="10.0.0.100",
            end_ip="10.0.0.200",
        )
    ],
    interfaces=[InterfaceData(id=1, vlan_id=1, name="eth0")],
    default_dns_servers=["10.0.0.2"],
    ntp_servers=["10.0.0.3"],
    ha_data=[
        KeaHAConfig(
            primary_rack_system_id="rack-1",
            secondary_rack_system_id="rack-2",
            primary_rack_ip="10.0.0.2",
            secondary_rack_ip="10.0.0.4",
        )
    ],
)


class InjectFakeTLSCN(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.scope.setdefault("extensions", {})
        request.scope["extensions"]["tls"] = {
            "client_cn": "01f09d32-f508-6064-bd1c-c025a58dd068"
        }
        return await call_next(request)


class InjectTLSWithoutClientCert(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.scope.setdefault("extensions", {})
        request.scope["extensions"]["tls"] = {}
        return await call_next(request)


@pytest.mark.asyncio
class TestRackControllersApi:
    BASE_PATH = f"{V3_INTERNAL_API_PREFIX}/rack_controllers"

    @pytest.fixture
    def internal_api_headers(self) -> dict:
        """Returns headers required for internal API requests"""
        return {"client-cert-cn": "test-client"}

    @patch(
        "maasapiserver.v3.api.internal.handlers.rackcontroller.ClusterConfiguration"
    )
    async def test_rack_controller_config_200_without_system_id(
        self,
        mock_cluster_config,
        services_mock: Mock,
        mocked_internal_api_client: AsyncClient,
        internal_app_with_mocked_services: FastAPI,
        internal_api_headers: dict,
    ) -> None:
        internal_app_with_mocked_services.add_middleware(InjectFakeTLSCN)
        mock_cluster_config.open.return_value.__enter__.return_value.temporal_server = "temporal.example:7233"
        mock_rack_controller = RackController(id=1, uuid=UUID, rack_id=1)
        services_mock.rack_controllers.get_one.return_value = (
            mock_rack_controller
        )
        services_mock.secrets.get_composite_secret.return_value = {
            "secret": "rpc-secret"
        }
        services_mock.configurations = AsyncMock()
        services_mock.configurations.get.return_value = (
            "http://maas.example:5240/MAAS"
        )

        response = await mocked_internal_api_client.get(
            f"{self.BASE_PATH}/{UUID}/config",
            headers=internal_api_headers,
        )

        assert response.status_code == 200
        response_json = response.json()
        assert response_json["maas_url"] == "http://maas.example:5240/MAAS"
        assert response_json["rpc_secret"] == "rpc-secret"
        assert response_json["system_id"] == ""
        assert "temporal" in response_json
        assert response_json["temporal"]["encryption_key"] == "rpc-secret"
        assert response_json["temporal"]["host"] == "temporal.example:7233"
        assert "ETag" in response.headers

    @patch(
        "maasapiserver.v3.api.internal.handlers.rackcontroller.ClusterConfiguration"
    )
    async def test_rack_controller_config_200_with_system_id(
        self,
        mock_cluster_config,
        services_mock: Mock,
        mocked_internal_api_client: AsyncClient,
        internal_app_with_mocked_services: FastAPI,
        internal_api_headers: dict,
    ) -> None:
        internal_app_with_mocked_services.add_middleware(InjectFakeTLSCN)
        mock_cluster_config.open.return_value.__enter__.return_value.temporal_server = "temporal.example:7233"
        mock_rack_controller = RackController(
            id=1, uuid=UUID, rack_id=1, node_id=42
        )
        services_mock.rack_controllers.get_one.return_value = (
            mock_rack_controller
        )
        mock_node = Mock(Node)
        mock_node.system_id = "system-id"
        services_mock.nodes.get_one.return_value = mock_node
        services_mock.secrets.get_composite_secret.return_value = {
            "secret": "rpc-secret"
        }
        services_mock.configurations = AsyncMock()
        services_mock.configurations.get.return_value = (
            "http://maas.example:5240/MAAS"
        )

        response = await mocked_internal_api_client.get(
            f"{self.BASE_PATH}/{UUID}/config",
            headers=internal_api_headers,
        )

        assert response.status_code == 200
        response_json = response.json()
        assert response_json["maas_url"] == "http://maas.example:5240/MAAS"
        assert response_json["rpc_secret"] == "rpc-secret"
        assert response_json["system_id"] == "system-id"
        assert "temporal" in response_json
        assert response_json["temporal"]["encryption_key"] == "rpc-secret"
        assert response_json["temporal"]["host"] == "temporal.example:7233"
        assert "ETag" in response.headers
        services_mock.nodes.get_one.assert_called_once()

    async def test_rack_controller_config_404(
        self,
        services_mock: Mock,
        mocked_internal_api_client: AsyncClient,
        internal_app_with_mocked_services: FastAPI,
        internal_api_headers: dict,
    ) -> None:
        internal_app_with_mocked_services.add_middleware(InjectFakeTLSCN)
        services_mock.rack_controllers.get_one.return_value = None

        nonexistent_uuid = "no-uuid"
        response = await mocked_internal_api_client.get(
            f"{self.BASE_PATH}/{nonexistent_uuid}/config",
            headers=internal_api_headers,
        )

        assert response.status_code == 404
        response_json = response.json()
        assert "details" in response_json
        assert (
            response_json["details"][0]["type"]
            == UNEXISTING_RESOURCE_VIOLATION_TYPE
        )
        assert (
            response_json["details"][0]["message"]
            == f"Could not find rack controller with UUID {nonexistent_uuid}."
        )

    async def test_rack_controller_config_503(
        self,
        services_mock: Mock,
        mocked_internal_api_client: AsyncClient,
        internal_app_with_mocked_services: FastAPI,
        internal_api_headers: dict,
    ) -> None:
        internal_app_with_mocked_services.add_middleware(InjectFakeTLSCN)

        mock_rack_controller = RackController(id=1, uuid=UUID, rack_id=1)
        services_mock.rack_controllers.get_one.return_value = (
            mock_rack_controller
        )
        services_mock.configurations = AsyncMock()
        services_mock.configurations.get.return_value = (
            "http://maas.example:5240/MAAS"
        )
        services_mock.secrets.get_composite_secret.return_value = None

        response = await mocked_internal_api_client.get(
            f"{self.BASE_PATH}/{UUID}/config",
            headers=internal_api_headers,
        )

        assert response.status_code == 503
        response_json = response.json()
        assert "details" in response_json
        assert response_json["details"][0]["type"] == PRECONDITION_FAILED
        assert (
            response_json["details"][0]["message"]
            == "RPC secret is not configured. Please ensure MAAS is properly initialized."
        )

    async def test_rack_controller_dhcp_data_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_internal_api_client: AsyncClient,
        internal_app_with_mocked_services: FastAPI,
    ) -> None:
        internal_app_with_mocked_services.add_middleware(InjectFakeTLSCN)
        services_mock.dhcp = Mock(DHCPService)
        services_mock.dhcp.get_kea_dhcp_data_for_rack_controller.return_value = DHCP_DATA

        response = await mocked_internal_api_client.get(
            f"{self.BASE_PATH}/rack-1/dhcp_data"
        )

        assert response.status_code == 200
        response_json = response.json()
        assert response_json["kind"] == "RackControllerDHCPData"
        assert response_json["vlans"] == [
            {"id": 1, "vid": 0, "relayed_vlan_id": None, "mtu": 1500}
        ]
        assert response_json["subnets"][0]["cidr"] == "10.0.0.0/24"
        assert response_json["subnets"][0]["pools"][0]["start_ip"] == (
            "10.0.0.100"
        )
        assert response_json["subnets"][0]["host_reservations"] == [
            {
                "ip": "10.0.0.10",
                "mac_address": "00:11:22:33:44:55",
                "hostname": "machine-1",
            }
        ]
        assert response_json["interfaces"] == [
            {"id": 1, "vlan_id": 1, "name": "eth0"}
        ]
        assert response_json["default_dns_servers"] == ["10.0.0.2"]
        assert response_json["ntp_servers"] == ["10.0.0.3"]
        assert response_json["ha_data"][0]["secondary_rack_ip"] == "10.0.0.4"
        assert response_json["_links"]["self"]["href"] == (
            f"{self.BASE_PATH}/rack-1/dhcp_data"
        )
        services_mock.dhcp.get_kea_dhcp_data_for_rack_controller.assert_called_once_with(
            "rack-1"
        )

    async def test_rack_controller_dhcp_data_requires_client_certificate(
        self,
        services_mock: ServiceCollectionV3,
        mocked_internal_api_client: AsyncClient,
        internal_app_with_mocked_services: FastAPI,
    ) -> None:
        internal_app_with_mocked_services.add_middleware(
            InjectTLSWithoutClientCert
        )
        services_mock.dhcp = Mock(DHCPService)

        response = await mocked_internal_api_client.get(
            f"{self.BASE_PATH}/rack-1/dhcp_data"
        )

        assert response.status_code == 403
        services_mock.dhcp.get_kea_dhcp_data_for_rack_controller.assert_not_called()

    async def test_rack_controller_dhcp_data_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_internal_api_client: AsyncClient,
        internal_app_with_mocked_services: FastAPI,
    ) -> None:
        internal_app_with_mocked_services.add_middleware(InjectFakeTLSCN)
        services_mock.dhcp = Mock(DHCPService)
        services_mock.dhcp.get_kea_dhcp_data_for_rack_controller.side_effect = NotFoundException()

        response = await mocked_internal_api_client.get(
            f"{self.BASE_PATH}/missing/dhcp_data"
        )

        assert response.status_code == 404

    async def test_rack_controller_dhcp_data_422_when_rack_not_configured(
        self,
        services_mock: ServiceCollectionV3,
        mocked_internal_api_client: AsyncClient,
        internal_app_with_mocked_services: FastAPI,
    ) -> None:
        internal_app_with_mocked_services.add_middleware(InjectFakeTLSCN)
        services_mock.dhcp = Mock(DHCPService)
        services_mock.dhcp.get_kea_dhcp_data_for_rack_controller.side_effect = ValidationException.build_for_field(
            "system_id",
            "The rack controller has no current configuration.",
        )

        response = await mocked_internal_api_client.get(
            f"{self.BASE_PATH}/rack-1/dhcp_data"
        )

        assert response.status_code == 422

    @patch(
        "maasapiserver.v3.api.internal.handlers.rackcontroller.sign_certificate_request"
    )
    @patch(
        "maasapiserver.v3.api.internal.handlers.rackcontroller.fetch_maas_ca_cert",
        new_callable=AsyncMock,
    )
    @patch(
        "maasapiserver.v3.api.internal.handlers.rackcontroller.crypto.dump_certificate",
    )
    async def test_rack_controller_enrollment_success(
        self,
        mock_dump_certificate,
        mock_fetch_maas_ca_cert,
        mock_sign_certificate_request,
        services_mock: Mock,
        mocked_internal_api_client: AsyncClient,
        internal_api_headers: dict,
    ) -> None:
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

        mock_token = BootstrapToken(
            id=1,
            secret="test-secret",
            rack_id=1,
            expires_at=utcnow() + timedelta(minutes=5),
        )
        services_mock.bootstraptokens.get_one.return_value = mock_token
        mock_rack = Rack(id=1, name="test-rack")
        services_mock.racks.get_one.return_value = mock_rack
        mock_ca_secret = {
            "key": "mock-key",
            "cert": "mock-cert",
            "cacert": "mock-cacert",
        }
        services_mock.secrets.get_composite_secret.return_value = (
            mock_ca_secret
        )
        mock_rack_controller = RackController(id=1, uuid=UUID, rack_id=1)
        services_mock.rack_controllers.create.return_value = (
            mock_rack_controller
        )

        request_data = {"secret": "test-secret", "csr": CSR}
        response = await mocked_internal_api_client.post(
            f"{self.BASE_PATH}:enroll",
            json=request_data,
            headers=internal_api_headers,
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

    async def test_rack_controller_enrollment_failed_with_not_found_secret(
        self,
        services_mock: Mock,
        mocked_internal_api_client: AsyncClient,
        internal_api_headers: dict,
    ) -> None:
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

    async def test_rack_controller_enrollment_with_expired_secret(
        self,
        services_mock: Mock,
        mocked_internal_api_client: AsyncClient,
        internal_api_headers: dict,
    ) -> None:
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

    @patch("maasapiserver.v3.api.internal.handlers.rackcontroller.logger")
    async def test_rack_controller_enrollment_token_reuse_logging(
        self,
        mock_logger,
        services_mock: Mock,
        mocked_internal_api_client: AsyncClient,
        internal_api_headers: dict,
    ) -> None:
        """Test that bootstrap token reuse is logged when token is expired."""
        mock_token = BootstrapToken(
            id=1,
            secret="test-secret",
            rack_id=1,
            expires_at=utcnow() - timedelta(minutes=5),
        )
        services_mock.bootstraptokens.get_one.return_value = mock_token

        request_data = {"secret": "test-secret", "csr": CSR}
        response = await mocked_internal_api_client.post(
            f"{self.BASE_PATH}:enroll",
            json=request_data,
            headers=internal_api_headers,
        )
        assert response.status_code == 401

        mock_logger.info.assert_called_once_with(
            f"{AUTHN_TOKEN_REUSED}:{BOOTSTRAP_TOKEN}",
            type=SECURITY,
            token_hash=hash_token_for_logging(mock_token.secret),
        )
