#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from httpx import AsyncClient
import pytest

from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestMain:
    async def test_openapi(
        self, api_client: AsyncClient, fixture: Fixture
    ) -> None:
        response = await api_client.get("/openapi.json")
        assert response.status_code == 200

        openapi_json = response.json()
        assert len(openapi_json["paths"]) > 0
        for path, specs in openapi_json["paths"].items():
            assert path.startswith("/MAAS/a")
            assert specs is not None
