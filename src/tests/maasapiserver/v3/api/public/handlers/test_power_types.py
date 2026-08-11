#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.services import ServiceCollectionV3
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)


class TestPowerTypesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/power-types"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [Endpoint(method="GET", path=self.BASE_PATH)]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_power_types(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.power_types = AsyncMock()
        services_mock.power_types.list.return_value = [
            {
                "driver_type": "power",
                "name": "ipmi",
                "description": "IPMI",
                "fields": [],
                "chassis": False,
                "can_probe": False,
                "missing_packages": [],
                "queryable": False,
                "fips_supported": True,
                "fips_unsupported_reason": None,
            },
            {
                "driver_type": "power",
                "name": "apc",
                "description": "APC",
                "fields": [],
                "chassis": True,
                "can_probe": False,
                "missing_packages": [],
                "queryable": False,
                "fips_supported": False,
                "fips_unsupported_reason": "SNMPv1",
            },
        ]

        response = await mocked_api_client_user.get(self.BASE_PATH)
        assert response.status_code == 200
        body = response.json()
        items = body["items"]
        assert len(items) == 2
        assert items[0]["fips_supported"] is True
        assert items[0]["fips_unsupported_reason"] is None
        assert items[1]["fips_supported"] is False
        assert items[1]["fips_unsupported_reason"] == "SNMPv1"
