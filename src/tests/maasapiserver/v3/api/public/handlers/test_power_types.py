#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import V3_API_PREFIX

BASE_PATH = f"{V3_API_PREFIX}/power-types"


@pytest.mark.asyncio
class TestPowerTypesHandler:
    async def test_list_power_types_unauthenticated(
        self,
        mocked_api_client: AsyncClient,
    ) -> None:
        response = await mocked_api_client.get(BASE_PATH)
        assert response.status_code == 401

    async def test_list_power_types(
        self,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        response = await mocked_api_client_user.get(BASE_PATH)
        assert response.status_code == 200

        power_types = {
            entry["name"]: entry for entry in response.json()["power_types"]
        }

        # Response shape
        for entry in power_types.values():
            assert "name" in entry
            assert "description" in entry
            assert "fips_supported" in entry
            assert "fips_unsupported_reason" in entry

        # Sorted order
        names = list(power_types)
        assert names == sorted(names)

        # Known unsupported driver
        assert power_types["apc"]["fips_supported"] is False
        assert power_types["apc"]["fips_unsupported_reason"] is not None

        # Known compliant driver
        assert power_types["redfish"]["fips_supported"] is True
        assert power_types["redfish"]["fips_unsupported_reason"] is None
