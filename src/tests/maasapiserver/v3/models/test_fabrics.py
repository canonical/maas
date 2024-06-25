# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import datetime

from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.fabrics import Fabric


class TestFabricsModel:
    def test_to_response(self) -> None:
        now = datetime.datetime.utcnow()
        fabric = Fabric(
            id=1,
            name="my fabric",
            description="my description",
            class_type="test",
            created=now,
            updated=now,
        )

        response = fabric.to_response(f"{V3_API_PREFIX}/fabrics")
        assert fabric.id == response.id
        assert fabric.name == response.name
        assert fabric.description == response.description
        assert response.hal_links.self.href == f"{V3_API_PREFIX}/fabrics/1"
