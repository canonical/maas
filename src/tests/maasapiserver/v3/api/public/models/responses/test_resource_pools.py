import datetime

from maasapiserver.v3.api.public.models.responses.resource_pools import (
    ResourcePoolPermission,
    ResourcePoolResponse,
    ResourcePoolWithSummaryResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.resource_pools import (
    ResourcePool,
    ResourcePoolWithSummary,
)


class TestResourcePoolsResponse:
    def test_from_model(self) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        resource_pool = ResourcePool(
            id=1,
            name="my resource_pools",
            description="my description",
            created=now,
            updated=now,
        )

        response = ResourcePoolResponse.from_model(
            resource_pool=resource_pool, self_base_hyperlink=V3_API_PREFIX
        )
        assert resource_pool.id == response.id
        assert resource_pool.name == response.name
        assert resource_pool.description == response.description
        assert response.hal_links.self.href == f"{V3_API_PREFIX}/1"

    def test_etag(self) -> None:
        now = datetime.datetime.fromtimestamp(1705671128)
        resource_pool = ResourcePool(
            id=1,
            name="my resource pools",
            description="my description",
            created=now,
            updated=now,
        )

        assert (
            resource_pool.etag()
            == "979626792c99c0860c39341ea26ae63a1ef7ca922d156b969777c05db3bee295"
        )


class TestResourcePoolsWithSummaryResponse:
    def test_from_model_with_summary(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        resource_pool_with_summary = ResourcePoolWithSummary(
            id=1,
            name="my resource_pools",
            description="my description",
            created=now,
            updated=now,
            machine_total_count=20,
            machine_ready_count=10,
        )

        response = ResourcePoolWithSummaryResponse.from_model_with_summary(
            resource_pool_with_summary=resource_pool_with_summary,
            permissions={ResourcePoolPermission.DELETE},
            self_base_hyperlink=V3_API_PREFIX,
        )
        assert resource_pool_with_summary.id == response.id
        assert resource_pool_with_summary.name == response.name
        assert resource_pool_with_summary.description == response.description
        assert (
            resource_pool_with_summary.machine_total_count
            == response.machine_total_count
        )
        assert (
            resource_pool_with_summary.machine_ready_count
            == response.machine_ready_count
        )
        assert response.permissions == {ResourcePoolPermission.DELETE}
        assert response.is_default is False
        assert response.hal_links.self.href == f"{V3_API_PREFIX}/1"
