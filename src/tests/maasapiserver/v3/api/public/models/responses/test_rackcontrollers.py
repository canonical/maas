# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import uuid

from maasapiserver.v3.api.public.models.responses.rackcontrollers import (
    RackControllerResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.rackcontrollers import RackController
from maasservicelayer.utils.date import utcnow


class TestRackControllerResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        rack_controller = RackController(
            id=1,
            created=now,
            updated=now,
            uuid=str(uuid.uuid4()),
            rack_id=1,
            node_id=1,
        )
        rack_controller_response = RackControllerResponse.from_model(
            rack_controller=rack_controller,
            self_base_hyperlink=f"{V3_API_PREFIX}/racks",
        )
        assert rack_controller.id == rack_controller_response.id
        assert rack_controller.rack_id == rack_controller_response.rack_id
        assert rack_controller.node_id == rack_controller_response.node_id
