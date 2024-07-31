# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from ipaddress import IPv4Address

from maasapiserver.v3.api.models.responses.events import EventTypeLevelEnum
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.events import (
    EndpointChoicesEnum,
    Event,
    EventType,
    LoggingLevelEnum,
)


class TestEventModel:
    def test_to_response(self) -> None:
        now = datetime.now(timezone.utc)
        event = Event(
            id=1,
            created=now,
            updated=now,
            type=EventType(
                id=1,
                created=now,
                updated=now,
                name="type test",
                description="type description",
                level=LoggingLevelEnum.AUDIT,
            ),
            node_system_id="test",
            node_hostname="hostname",
            user_id=1,
            owner="test",
            ip_address=IPv4Address("127.0.0.1"),
            endpoint=EndpointChoicesEnum.API,
            user_agent="agent",
            description="descr",
            action="deploy",
        )
        response = event.to_response(f"{V3_API_PREFIX}/events")
        assert event.id == response.id
        assert event.created == response.created
        assert event.updated == response.updated
        assert event.node_system_id == response.node_system_id
        assert event.node_hostname == response.node_hostname
        assert event.user_id == response.user_id
        assert event.owner == response.owner
        assert event.ip_address == response.ip_address
        assert event.user_agent == response.user_agent
        assert event.description == response.description
        assert event.action == response.action
        assert event.type.name == response.type.name
        assert event.type.description == response.type.description
        assert response.type.level == EventTypeLevelEnum.AUDIT
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/events/{event.id}"
        )
