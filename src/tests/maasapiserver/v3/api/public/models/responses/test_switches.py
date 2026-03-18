# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.switches import (
    SwitchResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.switches import Switch, SwitchWithTargetImage
from maasservicelayer.utils.date import utcnow


class TestSwitchResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        switch = SwitchWithTargetImage(
            id=0,
            created=now,
            updated=now,
            target_image_id=1,
            target_image="onie/mellanox",
        )
        switch_response = SwitchResponse.from_model(
            switch=switch,
            self_base_hyperlink=f"{V3_API_PREFIX}/staticroutes",
        )
        assert switch.id == switch_response.id
        assert switch.target_image_id == switch_response.target_image_id
        assert switch.target_image == switch_response.target_image
        assert switch_response.hal_links is not None
        assert switch_response.hal_links.self.href.endswith(
            f"staticroutes/{switch.id}"
        )

    def test_from_switch_model(self) -> None:
        now = utcnow()
        switch = Switch(
            id=0,
            created=now,
            updated=now,
            target_image_id=1,
        )
        switch_response = SwitchResponse.from_switch_model(
            switch=switch,
            target_image="onie/mellanox",
            self_base_hyperlink=f"{V3_API_PREFIX}/staticroutes",
        )
        assert switch.id == switch_response.id
        assert switch.target_image_id == switch_response.target_image_id
        assert switch_response.target_image == "onie/mellanox"
        assert switch_response.hal_links is not None
        assert switch_response.hal_links.self.href.endswith(
            f"staticroutes/{switch.id}"
        )
