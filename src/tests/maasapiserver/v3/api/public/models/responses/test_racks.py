# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.racks import RackResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.racks import Rack
from maasservicelayer.utils.date import utcnow


class TestRackResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        rack = Rack(
            id=1,
            created=now,
            updated=now,
            name="rack-008",
        )
        rack_response = RackResponse.from_model(
            rack=rack,
            self_base_hyperlink=f"{V3_API_PREFIX}/racks",
        )
        assert rack.id == rack_response.id
        assert rack.name == rack_response.name
