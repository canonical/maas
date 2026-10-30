#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasservicelayer.builders.events import EventBuilder
from maasservicelayer.db.mappers.event import EventDomainDataMapper
from maasservicelayer.db.tables import EventTable
from maasservicelayer.models.events import Event, EventType, LoggingLevelEnum


class TestEventDomainDataMapper:
    @pytest.fixture
    def mapper(self) -> EventDomainDataMapper:
        return EventDomainDataMapper(Event, EventTable)

    def test_build_resource(self, mapper: EventDomainDataMapper):
        evt = EventType(
            id=1,
            name="TEST_EVENT",
            description="test event",
            level=LoggingLevelEnum.INFO,
        )
        builder = EventBuilder(type=evt, owner="user1")
        res = mapper.build_resource(builder)
        assert "type_id" in res
        assert res["type_id"] == 1
        assert "username" in res
        assert res["username"] == "user1"

    @pytest.mark.parametrize("owner", [None, "projected-owner"])
    def test_to_domain_owner_mapping_does_not_mutate_row(
        self, mapper: EventDomainDataMapper, owner: str | None
    ):
        row = {
            "id": 1,
            "type": {
                "id": 2,
                "name": "TEST_EVENT",
                "description": "test event",
                "level": LoggingLevelEnum.INFO,
            },
            "username": "stored-owner",
            "node_hostname": "node",
            "endpoint": 0,
            "user_agent": "",
            "description": "event",
            "action": "",
        }
        if owner is not None:
            row["owner"] = owner
        original = row.copy()

        event = mapper.to_domain(row)

        assert event.owner == (owner or "stored-owner")
        assert event.type.id == 2
        assert row == original
