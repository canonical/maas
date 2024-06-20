import datetime

from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.zones import Zone


class TestZonesModel:
    def test_to_response(self) -> None:
        now = datetime.datetime.utcnow()
        zone = Zone(
            id=1,
            name="my zone",
            description="my description",
            created=now,
            updated=now,
        )

        response = zone.to_response(f"{V3_API_PREFIX}/")
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
