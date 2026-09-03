#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from unittest.mock import Mock, patch

from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import V3_API_PREFIX
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)


class TestSystemApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/system/info"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [Endpoint(method="GET", path=self.BASE_PATH)]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_get_system_info_user(
        self,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        conf = {
            "api_tls_dhparam": "/etc/maas/dhparam.pem",
            "api_bind": ["10.0.0.1"],
            "api_bind6": [],
            "prometheus_bind": "127.0.0.1",
            "temporal_bind": "",
            "rpc_bind": [],
            "agent_api_bind": [],
            "agent_api_bind6": [],
            "dns_bind": [],
            "dns_bind6": [],
            "syslog_bind": [],
            "http_proxy_bind": [],
            "http_proxy_bind6": [],
            "database_sslmode": "verify-full",
            "database_sslcert": "",
            "database_sslkey": "",
            "database_sslrootcert": "",
        }
        with patch(
            "maasapiserver.v3.api.public.handlers.system.get_fips_status"
        ) as mock_fips:
            with patch(
                "maasapiserver.v3.api.public.handlers.system.get_running_version"
            ) as mock_version:
                with patch(
                    "maasapiserver.v3.api.public.handlers.system.is_hardening_enabled"
                ) as mock_hardening:
                    with patch(
                        "maasapiserver.v3.api.public.handlers.system._read_hardening_conf",
                        return_value=conf,
                    ):
                        mock_hardening.return_value = True
                        mock_version.return_value = Mock(short_version="3.7.2")
                        mock_fips.return_value = Mock(enabled=True)
                        response = await mocked_api_client_user.get(
                            self.BASE_PATH
                        )

        assert response.status_code == 200
        body = response.json()
        assert body["fips_active"] is True
        assert body["version"] == "3.7.2"
        assert body["hardening_configuration"] is None
        assert body["hardening_active"] is True

    async def test_get_system_info_admin(
        self,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        conf = {
            "api_tls_dhparam": "/etc/maas/dhparam.pem",
            "api_bind": ["10.0.0.1"],
            "api_bind6": [],
            "prometheus_bind": "127.0.0.1",
            "temporal_bind": "",
            "rpc_bind": [],
            "agent_api_bind": [],
            "agent_api_bind6": [],
            "dns_bind": [],
            "dns_bind6": [],
            "syslog_bind": [],
            "http_proxy_bind": [],
            "http_proxy_bind6": [],
            "database_sslmode": "verify-full",
            "database_sslcert": "",
            "database_sslkey": "",
            "database_sslrootcert": "",
        }
        with patch(
            "maasapiserver.v3.api.public.handlers.system.get_fips_status"
        ) as mock_fips:
            with patch(
                "maasapiserver.v3.api.public.handlers.system.get_running_version"
            ) as mock_version:
                with patch(
                    "maasapiserver.v3.api.public.handlers.system.is_hardening_enabled"
                ) as mock_hardening:
                    with patch(
                        "maasapiserver.v3.api.public.handlers.system._read_hardening_conf",
                        return_value=conf,
                    ):
                        mock_hardening.return_value = True
                        mock_version.return_value = Mock(short_version="3.7.2")
                        mock_fips.return_value = Mock(enabled=True)
                        response = await mocked_api_client_admin.get(
                            self.BASE_PATH
                        )

        assert response.status_code == 200
        body = response.json()
        assert body["fips_active"] is True
        assert body["version"] == "3.7.2"
        assert body["hardening_configuration"] == {**conf}
        assert body["hardening_active"] is True

    async def test_get_system_info_not_authenticated(
        self, mocked_api_client: AsyncClient
    ) -> None:
        response = await mocked_api_client.get(self.BASE_PATH)
        assert response.status_code == 401
