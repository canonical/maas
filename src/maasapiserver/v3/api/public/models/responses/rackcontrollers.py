# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.rackcontrollers import RackController


class RackControllerResponse(HalResponse[BaseHal]):
    kind: str = Field(default="RackController")
    id: int
    rack_id: int
    node_id: int | None = None  # WIP: remove Optional once MAE is complete

    @classmethod
    def from_model(
        cls, rack_controller: RackController, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=rack_controller.id,
            rack_id=rack_controller.rack_id,
            node_id=rack_controller.node_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{rack_controller.id}"
                )
            ),
        )


class RackControllerListResponse(PaginatedResponse[RackControllerResponse]):
    kind: str = Field(default="RackControllerList")
