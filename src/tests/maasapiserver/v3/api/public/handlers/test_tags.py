# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.responses.tags import (
    TagResponse,
    TagsListResponse,
)
from maasapiserver.v3.auth.base import V3_API_PREFIX
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.tags import Tag
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.tags import TagsService
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

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


class TestTagsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/tags"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/2"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="PUT", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="POST", path=f"{self.BASE_PATH}"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/2"),
        ]

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.tags = Mock(TagsService)
        services_mock.tags.list.return_value = ListResult[Tag](
            items=[AUTOMATIC_TAG], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        tags_response = TagsListResponse(**response.json())
        assert len(tags_response.items) == 1
        assert tags_response.total == 2
        assert tags_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.tags = Mock(TagsService)
        services_mock.tags.list.return_value = ListResult[Tag](
            items=[AUTOMATIC_TAG, MANUAL_TAG], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=2")
        assert response.status_code == 200
        tags_response = TagsListResponse(**response.json())
        assert len(tags_response.items) == 2
        assert tags_response.total == 2
        assert tags_response.next is None

    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.tags = Mock(TagsService)
        services_mock.tags.get_by_id.return_value = AUTOMATIC_TAG
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        tag_response = TagResponse(**response.json())
        assert tag_response.id == 1

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.tags = Mock(TagsService)
        services_mock.tags.get_by_id.return_value = None
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_put_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.tags = Mock(TagsService)
        services_mock.tags.get_by_id.return_value = MANUAL_TAG
        updated = MANUAL_TAG.copy()
        updated.name = "new_name"
        services_mock.tags.update_by_id.return_value = updated

        update_request = {
            "name": "new_name",
            "comment": "comment",
            "definition": "",
            "kernel_opts": "console=tty0",
        }
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1",
            json=jsonable_encoder(update_request),
        )

        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0

        updated_tag_response = TagResponse(**response.json())
        assert updated_tag_response.id == updated.id
        assert updated_tag_response.name == updated.name

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.tags = Mock(TagsService)
        services_mock.tags.update_by_id.side_effect = NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                    message="Resource with such identifiers does not exist.",
                )
            ]
        )

        update_request = {
            "name": "new_name",
            "comment": "comment",
            "definition": "",
            "kernel_opts": "console=tty0",
        }
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1",
            json=jsonable_encoder(update_request),
        )
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_post_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.tags = Mock(TagsService)
        services_mock.tags.create.return_value = MANUAL_TAG

        create_request = {
            "name": "test-manual-tag",
            "comment": "comment",
            "definition": "",
            "kernel_opts": "console=tty0",
        }
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(create_request)
        )
        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0
        tag_response = TagResponse(**response.json())
        assert tag_response.name == create_request["name"]
        assert tag_response.definition == create_request["definition"]
        assert (
            tag_response.hal_links.self.href
            == f"{self.BASE_PATH}/{tag_response.id}"
        )

    async def test_post_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.tags = Mock(TagsService)
        services_mock.tags.create.side_effect = AlreadyExistsException(
            details=[
                BaseExceptionDetail(
                    type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                    message="A resource with such identifiers already exist.",
                )
            ]
        )
        create_request = {
            "name": "test-manual-tag",
            "comment": "comment",
            "definition": "",
            "kernel_opts": "console=tty0",
        }
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(create_request)
        )
        assert response.status_code == 409

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409

    async def test_delete_resource(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.tags = Mock(TagsService)
        services_mock.tags.delete_by_id.side_effect = None
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/100"
        )
        assert response.status_code == 204

    async def test_delete_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.tags = Mock(TagsService)
        services_mock.tags.delete_by_id.side_effect = [
            PreconditionFailedException(
                details=[
                    BaseExceptionDetail(
                        type=ETAG_PRECONDITION_VIOLATION_TYPE,
                        message="The resource etag 'wrong_etag' did not match 'my_etag'.",
                    )
                ]
            ),
            None,
        ]

        failed_response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/100",
            headers={"if-match": "wrong_etag"},
        )
        assert failed_response.status_code == 412
        error_response = ErrorBodyResponse(**failed_response.json())
        assert error_response.code == 412
        assert error_response.message == "A precondition has failed."
        assert (
            error_response.details[0].type == ETAG_PRECONDITION_VIOLATION_TYPE
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/100",
            headers={"if-match": "my_etag"},
        )
        assert response.status_code == 204
