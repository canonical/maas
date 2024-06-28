from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import V3_API_PREFIX


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestRootApi:
    async def test_get(self, api_client: AsyncClient) -> None:
        response = await api_client.get(f"{V3_API_PREFIX}/")
        assert response.status_code == 200
        assert response.json() == {}
