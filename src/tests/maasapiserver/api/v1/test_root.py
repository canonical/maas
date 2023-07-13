from httpx import AsyncClient
import pytest


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestRootApi:
    async def test_get(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/api/v1/")
        assert response.status_code == 200
        assert response.json() == {}
