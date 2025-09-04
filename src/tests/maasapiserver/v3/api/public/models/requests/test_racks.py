# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.racks import RackRequest


class TestRackRequest:
    def test_to_builder(self) -> None:
        rack_request = RackRequest(
            name="rack-01",
        )
        builder = rack_request.to_builder()
        assert rack_request.name == builder.name

    def test_mandatory_params(self) -> None:
        with pytest.raises(ValidationError) as e:
            RackRequest()

        assert len(e.value.errors()) == 1
        assert e.value.errors()[0]["loc"][0] == "name"
