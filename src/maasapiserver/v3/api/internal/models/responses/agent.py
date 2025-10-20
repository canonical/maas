# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
)
from maasservicelayer.models.agents import Agent


class AgentResponse(HalResponse[BaseHal]):
    kind = "Agent"
    id: int
    rack_id: int
    rackcontroller_id: Optional[int]

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


class AgentSignedCertificateResponse(HalResponse[BaseHal]):
    kind = "AgentSignedCertificate"
    certificate: str

    @classmethod
    def from_model(cls, certificate: str, self_base_hyperlink: str) -> Self:
        return cls(
            certificate=certificate,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(href=f"{self_base_hyperlink.rstrip('/')}")
            ),
        )
