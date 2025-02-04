from maasservicelayer.builders.events import EventBuilder
from maasservicelayer.db.mappers.event import EventDomainDataMapper
from maasservicelayer.db.tables import EventTable
from maasservicelayer.models.events import EventType, LoggingLevelEnum


class TestEventDomainDataMapper:

    def test_build_resource(self):
        evt = EventType(
            id=1,
            name="TEST_EVENT",
            description="test event",
            level=LoggingLevelEnum.INFO,
        )
        mapper = EventDomainDataMapper(EventTable)
        builder = EventBuilder(type=evt, owner="user1")
        res = mapper.build_resource(builder)
        assert "type_id" in res
        assert res["type_id"] == 1
        assert "username" in res
        assert res["username"] == "user1"
