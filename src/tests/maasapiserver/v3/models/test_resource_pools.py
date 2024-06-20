import datetime

from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.resource_pools import ResourcePool


class TestResourcePoolsModel:
    def test_to_response(self) -> None:
        now = datetime.datetime.utcnow()
        resource_pools = ResourcePool(
            id=1,
            name="my resource_pools",
            description="my description",
            created=now,
            updated=now,
        )

        response = resource_pools.to_response(V3_API_PREFIX)
        assert resource_pools.id == response.id
        assert resource_pools.name == response.name
        assert resource_pools.description == response.description
        assert response.hal_links.self.href == f"{V3_API_PREFIX}/1"

    def test_etag(self) -> None:
        now = datetime.datetime.fromtimestamp(1705671128)
        resource_pools = ResourcePool(
            id=1,
            name="my resource pools",
            description="my description",
            created=now,
            updated=now,
        )

        assert (
            resource_pools.etag()
            == "979626792c99c0860c39341ea26ae63a1ef7ca922d156b969777c05db3bee295"
        )
