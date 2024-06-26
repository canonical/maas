# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.spaces import Space


class TestSpaceModel:
    def test_to_response(self) -> None:
        now = datetime.now(timezone.utc)
        space = Space(
            id=1,
            name="my space",
            description="space description",
            created=now,
            updated=now,
        )
        response = space.to_response(f"{V3_API_PREFIX}/spaces")
        assert space.id == response.id
        assert space.name == response.name
        assert space.description == response.description
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/spaces/{space.id}"
        )
