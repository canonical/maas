# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.agents import Agent


class AgentResponse(HalResponse[BaseHal]):
    kind = "Agent"
    id: int
    rack_id: int
    rackcontroller_id: Optional[
        int
    ]  # WIP: remove Optional once MAE is complete

    @classmethod
    def from_model(cls, agent: Agent, self_base_hyperlink: str) -> Self:
        return cls(
            id=agent.id,
            rack_id=agent.rack_id,
            rackcontroller_id=agent.rackcontroller_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{agent.id}"
                )
            ),
        )


class AgentListResponse(PaginatedResponse[AgentResponse]):
    kind = "AgentList"
