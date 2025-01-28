import datetime

from maasapiserver.v3.api.public.models.responses.zones import (
    ZoneResponse,
    ZoneWithSummaryResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.zones import Zone, ZoneWithSummary


class TestZonesResponse:
    def test_from_model(self) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        zone = Zone(
            id=1,
            name="my zone",
            description="my description",
            created=now,
            updated=now,
        )

        response = ZoneResponse.from_model(
            zone=zone, self_base_hyperlink=f"{V3_API_PREFIX}/"
        )
        assert zone.id == response.id
        assert zone.name == response.name
        assert zone.description == response.description
        assert response.hal_links.self.href == f"{V3_API_PREFIX}/1"

    def test_etag(self) -> None:
        now = datetime.datetime.fromtimestamp(1705671128)
        zone = Zone(
            id=1,
            name="my zone",
            description="my description",
            created=now,
            updated=now,
        )

        assert (
            zone.etag()
            == "979626792c99c0860c39341ea26ae63a1ef7ca922d156b969777c05db3bee295"
        )


class TestZonesWithSummaryResponse:
    def test_from_model(self) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        zone_with_summary = ZoneWithSummary(
            id=1,
            name="my zone",
            description="my description",
            machines_count=10,
            devices_count=20,
            controllers_count=30,
            created=now,
            updated=now,
        )

        response = ZoneWithSummaryResponse.from_model(
            zone_with_summary=zone_with_summary,
            self_base_hyperlink=f"{V3_API_PREFIX}/",
        )
        assert zone_with_summary.id == response.id
        assert zone_with_summary.name == response.name
        assert zone_with_summary.description == response.description
        assert zone_with_summary.machines_count == response.machines_count
        assert zone_with_summary.devices_count == response.devices_count
        assert (
            zone_with_summary.controllers_count == response.controllers_count
        )
        assert response.hal_links.self.href == f"{V3_API_PREFIX}/1"
