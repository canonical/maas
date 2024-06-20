from httpx import AsyncClient
import pytest

from maasapiserver.v2.constants import V2_API_PREFIX


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestRootApi:
    async def test_get(self, api_client: AsyncClient) -> None:
        response = await api_client.get(f"{V2_API_PREFIX}/")
        assert response.status_code == 200
        assert response.json() == {}
