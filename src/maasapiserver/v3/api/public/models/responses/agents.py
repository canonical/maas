# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

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
    secret: str
    rack_id: int
    rackcontroller_id: int

    @classmethod
    def from_model(cls, agent: Agent, self_base_hyperlink: str) -> Self:
        return cls(
            id=agent.id,
            secret=agent.secret,
            rack_id=agent.rack_id,
            rackcontroller_id=agent.rackcontroller_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{agent.id}"
                )
            ),
        )


class AgentsListResponse(PaginatedResponse[AgentResponse]):
    kind = "AgentList"
