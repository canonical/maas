# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

from maasapiserver.v3.api.public.models.responses.spaces import SpaceResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.spaces import Space


class TestSpaceResponse:
    def test_from_model(self) -> None:
        now = datetime.now(timezone.utc)
        space = Space(
            id=1,
            name="my space",
            description="space description",
            created=now,
            updated=now,
        )
        response = SpaceResponse.from_model(
            space=space, self_base_hyperlink=f"{V3_API_PREFIX}/spaces"
        )
        assert space.id == response.id
        assert space.name == response.name
        assert space.description == response.description
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/spaces/{space.id}"
        )
