#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import datetime

from maasapiserver.v3.api.public.models.responses.fabrics import FabricResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.fabrics import Fabric


class TestFabricsResponse:
    def test_from_model(self) -> None:
        now = datetime.datetime.utcnow()
        fabric = Fabric(
            id=1,
            name="my fabric",
            description="my description",
            class_type="test",
            created=now,
            updated=now,
        )

        response = FabricResponse.from_model(
            fabric=fabric, self_base_hyperlink=f"{V3_API_PREFIX}/fabrics"
        )
        assert fabric.id == response.id
        assert fabric.name == response.name
        assert fabric.description == response.description
        assert response.hal_links.self.href == f"{V3_API_PREFIX}/fabrics/1"
