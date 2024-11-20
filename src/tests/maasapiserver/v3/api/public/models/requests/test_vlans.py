#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.vlans import VlanCreateRequest


class TestVlanCreateRequest:
    def test_mandatory_params(self):
        with pytest.raises(ValidationError) as e:
            VlanCreateRequest()

        assert len(e.value.errors()) == 1
        assert e.value.errors()[0]["loc"][0] == "vid"

    def test_to_builder(self):
        resource = VlanCreateRequest(vid=0).to_builder().build()
        assert resource.get_values()["dhcp_on"] is False
        assert resource.get_values()["vid"] == 0
