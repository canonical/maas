# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.events import EventTypeEnum
from maascommon.workflows.tag import (
    TAG_EVALUATION_WORKFLOW_NAME,
    TagEvaluationParam,
)
from maasservicelayer.builders.tags import TagBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.tags import TagsRepository
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.tags import Tag
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.tags import TagsService
from maasservicelayer.services.temporal import TemporalService
from tests.maasservicelayer.services.base import ServiceCommonTests

AUTOMATIC_TAG = Tag(
    id=1,
    name="test-auto-tag",
    comment="comment",
    definition="//node",
    kernel_opts="console=tty0",
)

MANUAL_TAG = Tag(
    id=1,
    name="test-manual-tag",
    comment="comment",
    definition="",
    kernel_opts="console=tty0",
)


class TestTagsServiceCommon(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> TagsService:
        return TagsService(
            context=Context(),
            repository=Mock(TagsRepository),
            events_service=Mock(EventsService),
            temporal_service=Mock(TemporalService),
        )

    @pytest.fixture
    def test_instance(self) -> Tag:
        return AUTOMATIC_TAG

    @pytest.fixture
    def builder_model(self) -> type[TagBuilder]:
        return TagBuilder

    async def test_update_many(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(
                service_instance, test_instance, builder_model
            )

    async def test_delete_many(self, service_instance, test_instance):
        with pytest.raises(NotImplementedError):
            await super().test_delete_many(service_instance, test_instance)


@pytest.mark.asyncio
class TestTagsService:
    @pytest.fixture
    def tags_repository(self) -> Mock:
        return Mock(TagsRepository)

    @pytest.fixture
    def events_service(self) -> Mock:
        return Mock(EventsService)

    @pytest.fixture
    def temporal_mock(self) -> Mock:
        return Mock(TemporalService)

    @pytest.fixture
    def tags_service(
        self, tags_repository: Mock, temporal_mock: Mock, events_service: Mock
    ) -> TagsService:
        return TagsService(
            context=Context(),
            repository=tags_repository,
            events_service=events_service,
            temporal_service=temporal_mock,
        )

    @pytest.mark.parametrize(
        "tag,should_start",
        [
            (AUTOMATIC_TAG, True),
            (MANUAL_TAG, False),
        ],
    )
    async def test_start_tag_evaluation_workflow(
        self,
        temporal_mock: Mock,
        tags_service: TagsService,
        tag: Tag,
        should_start: bool,
    ) -> None:
        await tags_service._start_tag_evaluation_wf(tag)
        if should_start:
            temporal_mock.register_workflow_call.assert_called_once()
        else:
            temporal_mock.register_workflow_call.assert_not_called()

    async def test_create_automatic_tag(
        self,
        tags_repository: Mock,
        temporal_mock: Mock,
        events_service: Mock,
        tags_service: TagsService,
    ) -> None:
        tags_repository.create.return_value = AUTOMATIC_TAG
        temporal_mock.register_workflow_call.return_value = None
        builder = TagBuilder(
            name="test-automatic-tag",
            comment="comment",
            definition="//node",
            kernel_opts="console=tty0",
        )
        await tags_service.create(builder)

        temporal_mock.register_workflow_call.assert_called_once_with(
            workflow_name=TAG_EVALUATION_WORKFLOW_NAME,
            workflow_id="tag-evaluation",
            parameter=TagEvaluationParam(
                AUTOMATIC_TAG.id, AUTOMATIC_TAG.definition
            ),
        )
        events_service.record_event.assert_called_once_with(
            event_type=EventTypeEnum.TAG,
            event_description=f"Tag '{AUTOMATIC_TAG.name}' created.",
        )

    async def test_create_manual_tag(
        self,
        tags_repository: Mock,
        temporal_mock: Mock,
        events_service: Mock,
        tags_service: TagsService,
    ) -> None:
        tags_repository.create.return_value = MANUAL_TAG
        temporal_mock.register_workflow_call.return_value = None
        builder = TagBuilder(
            name="test-manual-tag",
            comment="comment",
            definition="",
            kernel_opts="console=tty0",
        )
        await tags_service.create(builder)

        temporal_mock.register_workflow_call.assert_not_called()
        events_service.record_event.assert_called_once_with(
            event_type=EventTypeEnum.TAG,
            event_description=f"Tag '{MANUAL_TAG.name}' created.",
        )

    async def test_update_automatic_tag_definition(
        self,
        tags_repository: Mock,
        temporal_mock: Mock,
        events_service: Mock,
        tags_service: TagsService,
    ) -> None:
        new_tag = AUTOMATIC_TAG.copy()
        new_tag.definition = '//node[@class="system"]'
        tags_repository.get_by_id.return_value = AUTOMATIC_TAG
        tags_repository.update_by_id.return_value = new_tag
        temporal_mock.register_workflow_call.return_value = None
        builder = TagBuilder(
            definition='//node[@class="system"]',
        )
        await tags_service.update_by_id(id=AUTOMATIC_TAG.id, builder=builder)

        temporal_mock.register_workflow_call.assert_called_once_with(
            workflow_name=TAG_EVALUATION_WORKFLOW_NAME,
            workflow_id="tag-evaluation",
            parameter=TagEvaluationParam(AUTOMATIC_TAG.id, new_tag.definition),
        )
        events_service.record_event.assert_called_once_with(
            event_type=EventTypeEnum.TAG,
            event_description=f"Tag '{AUTOMATIC_TAG.name}' updated.",
        )

    async def test_update_name(
        self,
        tags_repository: Mock,
        temporal_mock: Mock,
        events_service: Mock,
        tags_service: TagsService,
    ) -> None:
        new_tag = AUTOMATIC_TAG.copy()
        new_tag.name = "foo"
        tags_repository.get_by_id.return_value = AUTOMATIC_TAG
        tags_repository.update_by_id.return_value = new_tag
        temporal_mock.register_workflow_call.return_value = None
        builder = TagBuilder(
            name="foo",
        )
        await tags_service.update_by_id(id=AUTOMATIC_TAG.id, builder=builder)

        temporal_mock.register_workflow_call.assert_not_called()
        events_service.record_event.assert_called_once_with(
            event_type=EventTypeEnum.TAG,
            event_description=f"Tag '{AUTOMATIC_TAG.name}' renamed to '{new_tag.name}'.",
        )

    async def test_update_add_definition_to_manual_tag_raise_exc(
        self,
        tags_repository: Mock,
        temporal_mock: Mock,
        events_service: Mock,
        tags_service: TagsService,
    ) -> None:
        tags_repository.get_by_id.return_value = MANUAL_TAG
        temporal_mock.register_workflow_call.return_value = None
        builder = TagBuilder(definition="//node")
        with pytest.raises(ValidationException) as exc:
            await tags_service.update_by_id(id=MANUAL_TAG.id, builder=builder)
        assert exc.value.details[0].field == "definition"
        assert (
            exc.value.details[0].message
            == "Definitions can't be added to a manual tag. Consider creating a new tag."
        )
        temporal_mock.register_workflow_call.assert_not_called()
        events_service.record_event.assert_not_called()

    async def test_update_remove_definition_from_auto_tag_raise_exc(
        self,
        tags_repository: Mock,
        temporal_mock: Mock,
        events_service: Mock,
        tags_service: TagsService,
    ) -> None:
        tags_repository.get_by_id.return_value = AUTOMATIC_TAG
        temporal_mock.register_workflow_call.return_value = None
        builder = TagBuilder(
            definition="",
        )
        with pytest.raises(ValidationException) as exc:
            await tags_service.update_by_id(
                id=AUTOMATIC_TAG.id, builder=builder
            )
        assert exc.value.details[0].field == "definition"
        assert (
            exc.value.details[0].message
            == "Removing the definition of an automatic tag is not allowed. Consider creating a new tag."
        )
        temporal_mock.register_workflow_call.assert_not_called()
        events_service.record_event.assert_not_called()

    async def test_delete(
        self,
        tags_repository: Mock,
        events_service: Mock,
        tags_service: TagsService,
    ) -> None:
        tags_repository.get_by_id.return_value = AUTOMATIC_TAG
        tags_repository.delete_by_id.return_value = AUTOMATIC_TAG
        tags_repository.delete_nodes_relationship_for_tag.return_value = None

        await tags_service.delete_by_id(AUTOMATIC_TAG.id)

        tags_repository.delete_nodes_relationship_for_tag.assert_called_once_with(
            AUTOMATIC_TAG
        )
        events_service.record_event.assert_called_once_with(
            event_type=EventTypeEnum.TAG,
            event_description=f"Tag '{AUTOMATIC_TAG.name}' deleted.",
        )
