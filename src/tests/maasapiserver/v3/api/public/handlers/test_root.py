from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import V3_API_PREFIX


@pytest.mark.asyncio
class TestRootApi:
    async def test_get(self, mocked_api_client: AsyncClient) -> None:
        response = await mocked_api_client.get(f"{V3_API_PREFIX}/")
        assert response.status_code == 200
        assert response.json() == {}
