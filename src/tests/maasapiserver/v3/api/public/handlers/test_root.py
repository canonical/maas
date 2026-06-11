from unittest.mock import AsyncMock, Mock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.fips import FIPSStatus
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.fips import FIPSService


@pytest.mark.asyncio
class TestRootApi:
    async def test_get(
        self,
        mocked_api_client: AsyncClient,
        services_mock: ServiceCollectionV3,
    ) -> None:
        services_mock.fips = Mock(FIPSService)
        services_mock.fips.get_fips_status = AsyncMock(
            return_value=FIPSStatus(
                fips_enabled=False,
                detection_source="/proc/sys/crypto/fips_enabled",
            )
        )
        response = await mocked_api_client.get(f"{V3_API_PREFIX}/")
        assert response.status_code == 200
        assert response.json() == {"fips_active": False}

    async def test_get_fips_active_true(
        self,
        mocked_api_client: AsyncClient,
        services_mock: ServiceCollectionV3,
    ) -> None:
        services_mock.fips = Mock(FIPSService)
        services_mock.fips.get_fips_status = AsyncMock(
            return_value=FIPSStatus(
                fips_enabled=True,
                detection_source="/proc/sys/crypto/fips_enabled",
            )
        )

        response = await mocked_api_client.get(f"{V3_API_PREFIX}/")

        assert response.status_code == 200
        assert response.json() == {"fips_active": True}
