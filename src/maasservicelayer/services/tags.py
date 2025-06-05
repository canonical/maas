# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import override

from maascommon.enums.events import EventTypeEnum
from maascommon.workflows.tag import (
    TAG_EVALUATION_WORKFLOW_NAME,
    TagEvaluationParam,
)
from maasservicelayer.builders.tags import TagBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.tags import TagsRepository
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.base import Unset
from maasservicelayer.models.tags import Tag
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.temporal import TemporalService


class TagsService(BaseService[Tag, TagsRepository, TagBuilder]):
    def __init__(
        self,
        context: Context,
        repository: TagsRepository,
        events_service: EventsService,
        temporal_service: TemporalService,
    ):
        super().__init__(context, repository)
        self.events_service = events_service
        self.temporal_service = temporal_service

    async def _start_tag_evaluation_wf(self, tag: Tag) -> None:
        if tag.definition != "":
            return self.temporal_service.register_workflow_call(
                workflow_name=TAG_EVALUATION_WORKFLOW_NAME,
                workflow_id="tag-evaluation",
                parameter=TagEvaluationParam(tag.id, tag.definition),
            )

    @override
    async def post_create_hook(self, resource: Tag) -> None:
        await self._start_tag_evaluation_wf(resource)
        await self.events_service.record_event(
            event_type=EventTypeEnum.TAG,
            event_description=f"Tag '{resource.name}' created.",
        )

    @override
    async def post_update_hook(
        self, old_resource: Tag, updated_resource: Tag
    ) -> None:
        if updated_resource.definition != old_resource.definition:
            await self._start_tag_evaluation_wf(updated_resource)
        action = (
            f"renamed to '{updated_resource.name}'"
            if updated_resource.name != old_resource.name
            else "updated"
        )

        await self.events_service.record_event(
            event_type=EventTypeEnum.TAG,
            event_description=f"Tag '{old_resource.name}' {action}.",
        )

    @override
    async def post_update_many_hook(self, resources: list[Tag]) -> None:
        raise NotImplementedError("Not implemented yet.")

    @override
    async def pre_delete_hook(self, resource_to_be_deleted: Tag) -> None:
        await self.repository.delete_nodes_relationship_for_tag(
            resource_to_be_deleted
        )

    @override
    async def post_delete_hook(self, resource: Tag) -> None:
        await self.events_service.record_event(
            event_type=EventTypeEnum.TAG,
            event_description=f"Tag '{resource.name}' deleted.",
        )

    @override
    async def post_delete_many_hook(self, resources: list[Tag]) -> None:
        raise NotImplementedError("Not implemented yet.")

    @override
    async def _update_resource(
        self,
        existing_resource: Tag | None,
        builder: TagBuilder,
        etag_if_match: str | None = None,
    ) -> Tag:
        if existing_resource is not None and not isinstance(
            builder.definition, Unset
        ):
            if existing_resource.definition == "" and builder.definition != "":
                raise ValidationException.build_for_field(
                    field="definition",
                    message="Definitions can't be added to a manual tag. Consider creating a new tag.",
                )
            elif (
                existing_resource.definition != "" and builder.definition == ""
            ):
                raise ValidationException.build_for_field(
                    field="definition",
                    message="Removing the definition of an automatic tag is not allowed. Consider creating a new tag.",
                )
        return await super()._update_resource(
            existing_resource, builder, etag_if_match
        )
