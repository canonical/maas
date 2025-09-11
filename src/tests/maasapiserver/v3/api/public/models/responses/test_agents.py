# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.agents import AgentResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.agents import Agent
from maasservicelayer.utils.date import utcnow


class TestAgentResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        agent = Agent(
            id=1,
            created=now,
            updated=now,
            secret="secrete",
            rack_id=1,
            rackcontroller_id=1,
        )
        agent_response = AgentResponse.from_model(
            agent=agent,
            self_base_hyperlink=f"{V3_API_PREFIX}/racks",
        )
        assert agent.id == agent_response.id
        assert agent.secret == agent_response.secret
        assert agent.rack_id == agent_response.rack_id
        assert agent.rackcontroller_id == agent_response.rackcontroller_id
