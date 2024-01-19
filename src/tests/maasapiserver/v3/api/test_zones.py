import datetime

from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import EXTERNAL_V3_API_PREFIX


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestZonesApi:
    async def test_get_200(self, api_client: AsyncClient, fixture) -> None:
        created_at = datetime.datetime.utcnow().astimezone()
        updated_at = datetime.datetime.utcnow().astimezone()
        [created_zone] = await fixture.create(
            "maasserver_zone",
            [
                {
                    "name": "my_zone",
                    "description": "my_description",
                    "created": created_at,
                    "updated": updated_at,
                }
            ],
        )

        response = await api_client.get(f"/api/v3/zones/{created_zone['id']}")
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "Zone",
            "id": created_zone["id"],
            "name": "my_zone",
            "description": "my_description",
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "_links": {
                "self": {
                    "href": f"{EXTERNAL_V3_API_PREFIX}/zones/{created_zone['id']}"
                }
            },
        }

    async def test_get_400(self, api_client: AsyncClient, fixture) -> None:
        response = await api_client.get("/api/v3/zones/100")
        assert response.status_code == 404
        assert "ETag" not in response.headers

        response_body = response.json()
        assert response_body["kind"] == "Error"
        assert response_body["code"] == 404

    async def test_get_422(self, api_client: AsyncClient, fixture) -> None:
        response = await api_client.get("/api/v3/zones/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        response_body = response.json()
        assert response_body["kind"] == "Error"
        assert response_body["code"] == 422
