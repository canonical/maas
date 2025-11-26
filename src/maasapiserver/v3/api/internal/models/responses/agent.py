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


class AgentConfigResponse(HalResponse[BaseHal]):
    kind = "AgentSignedCertificate"
    maas_url: str
    rpc_secret: str
    system_id: str
    temporal: dict

    @classmethod
    def from_model(
        cls,
        maas_url: str,
        rpc_secret: str,
        system_id: str,
        temporal: dict,
        self_base_hyperlink: str,
    ) -> Self:
        return cls(
            maas_url=maas_url,
            rpc_secret=rpc_secret,
            system_id=system_id,
            temporal=temporal,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(href=f"{self_base_hyperlink.rstrip('/')}")
            ),
        )


class AgentSignedCertificateResponse(HalResponse[BaseHal]):
    kind = "AgentSignedCertificate"
    certificate: str
    ca: str

    @classmethod
    def from_model(
        cls, certificate: str, ca: str, self_base_hyperlink: str
    ) -> Self:
        return cls(
            certificate=certificate,
            ca=ca,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(href=f"{self_base_hyperlink.rstrip('/')}")
            ),
        )
