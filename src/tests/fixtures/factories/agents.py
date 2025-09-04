# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

from maasservicelayer.db.tables import AgentTable
from maasservicelayer.models.agents import Agent
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_agents_entry(
    fixture: Fixture,
    secret: str,
    rack_id: id,
    rackcontroller_id: int,
    **extra_details,
) -> Agent:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    agent = {
        "created": created_at,
        "updated": updated_at,
        "secret": secret,
        "rack_id": rack_id,
        "rackcontroller_id": rackcontroller_id,
    }
    agent.update(extra_details)

    [created_agent] = await fixture.create(AgentTable.name, agent)

    return Agent(**created_agent)
