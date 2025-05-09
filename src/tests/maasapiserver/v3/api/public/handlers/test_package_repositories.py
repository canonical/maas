#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.responses.package_repositories import (
    PackageRepositoryListResponse,
    PackageRepositoryResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.package_repositories import (
    PACKAGE_REPO_MAIN_ARCHES,
    PACKAGE_REPO_PORTS_ARCHES,
)
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BadRequestException,
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_PACKAGE_REPO_VIOLATION_TYPE,
    ETAG_PRECONDITION_VIOLATION_TYPE,
    INVALID_ARGUMENT_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.fields import PackageRepoUrl
from maasservicelayer.models.package_repositories import PackageRepository
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.package_repositories import (
    PackageRepositoriesService,
)
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

MAIN_PACKAGE_REPO = PackageRepository(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    name="main_archive",
    url=PackageRepoUrl("http://archive.ubuntu.com/ubuntu"),
    components=set(),
    arches=PACKAGE_REPO_MAIN_ARCHES,
    key="",
    default=True,
    enabled=True,
    disabled_pockets=set(),
    distributions=[],
    disabled_components=set(),
    disable_sources=True,
)

PORTS_PACKAGE_REPO = PackageRepository(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    name="ports_archive",
    url=PackageRepoUrl("http://ports.ubuntu.com/ubuntu-ports"),
    components=set(),
    arches=PACKAGE_REPO_PORTS_ARCHES,
    key="",
    default=True,
    enabled=True,
    disabled_pockets=set(),
    distributions=[],
    disabled_components=set(),
    disable_sources=True,
)

TEST_PACKAGE_REPO = PackageRepository(
    id=3,
    created=utcnow(),
    updated=utcnow(),
    name="test-main",
    key="test-key",
    url=PackageRepoUrl("http://archive.ubuntu.com/ubuntu"),
    distributions=[],
    components=set(),
    arches=set(),
    disabled_pockets=set(),
    disabled_components=set(),
    disable_sources=False,
    default=False,
    enabled=True,
)


class TestPackageRepositoriesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/package_repositories"

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
        services_mock.package_repositories = Mock(PackageRepositoriesService)
        services_mock.package_repositories.list.return_value = ListResult[
            PackageRepository
        ](items=[PORTS_PACKAGE_REPO], total=2)
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        package_repositories_response = PackageRepositoryListResponse(
            **response.json()
        )
        assert len(package_repositories_response.items) == 1
        assert package_repositories_response.total == 2
        assert (
            package_repositories_response.next
            == f"{self.BASE_PATH}?page=2&size=1"
        )

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.package_repositories = Mock(PackageRepositoriesService)
        services_mock.package_repositories.list.return_value = ListResult[
            PackageRepository
        ](items=[MAIN_PACKAGE_REPO, PORTS_PACKAGE_REPO], total=2)
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=2")
        assert response.status_code == 200
        package_repositories_response = PackageRepositoryListResponse(
            **response.json()
        )
        assert len(package_repositories_response.items) == 2
        assert package_repositories_response.total == 2
        assert package_repositories_response.next is None

    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.package_repositories = Mock(PackageRepositoriesService)
        services_mock.package_repositories.get_by_id.return_value = (
            MAIN_PACKAGE_REPO
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        pr_response = PackageRepositoryResponse(**response.json())
        assert pr_response.id == 1

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.package_repositories = Mock(PackageRepositoriesService)
        services_mock.package_repositories.get_by_id.return_value = None
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
        services_mock.package_repositories = Mock(PackageRepositoriesService)
        services_mock.package_repositories.get_by_id.return_value = (
            TEST_PACKAGE_REPO
        )
        updated = TEST_PACKAGE_REPO.copy()
        updated.name = "new_name"
        services_mock.package_repositories.update_by_id.return_value = updated

        update_request = {
            "name": "new_name",
            "key": "test-key",
            "url": "http://archive.ubuntu.com/ubuntu",
            "distributions": [],
            "components": set(),
            "arches": set(),
            "disabled_pockets": set(),
            "disabled_components": set(),
            "disable_sources": False,
            "enabled": True,
        }
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1",
            json=jsonable_encoder(update_request),
        )

        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0

        updated_pr_response = PackageRepositoryResponse(**response.json())
        assert updated_pr_response.id == updated.id
        assert updated_pr_response.name == updated.name

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.package_repositories = Mock(PackageRepositoriesService)
        services_mock.package_repositories.get_by_id.return_value = None
        update_request = {
            "name": "new_name",
            "key": "test-key",
            "url": "http://archive.ubuntu.com/ubuntu",
            "distributions": [],
            "components": set(),
            "arches": set(),
            "disabled_pockets": set(),
            "disabled_components": set(),
            "disable_sources": False,
            "enabled": True,
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
        services_mock.package_repositories = Mock(PackageRepositoriesService)
        services_mock.package_repositories.create.return_value = (
            TEST_PACKAGE_REPO
        )

        create_request = {
            "name": "test-main",
            "key": "test-key",
            "url": "http://archive.ubuntu.com/ubuntu",
            "distributions": [],
            "components": set(),
            "arches": set(),
            "disabled_pockets": set(),
            "disabled_components": set(),
            "disable_sources": False,
            "enabled": True,
        }
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(create_request)
        )
        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0
        pr_response = PackageRepositoryResponse(**response.json())
        assert pr_response.name == create_request["name"]
        assert pr_response.url == create_request["url"]
        assert (
            pr_response.hal_links.self.href
            == f"{self.BASE_PATH}/{pr_response.id}"
        )

    async def test_post_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.package_repositories = Mock(PackageRepositoriesService)
        services_mock.package_repositories.create.side_effect = AlreadyExistsException(
            details=[
                BaseExceptionDetail(
                    type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                    message="A resource with such identifiers already exist.",
                )
            ]
        )
        create_request = {
            "name": "test-main",
            "key": "test-key",
            "url": "http://archive.ubuntu.com/ubuntu",
            "distributions": [],
            "components": set(),
            "arches": set(),
            "disabled_pockets": set(),
            "disabled_components": set(),
            "disable_sources": False,
            "enabled": True,
        }
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(create_request)
        )
        assert response.status_code == 409

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409
        BadRequestException(
            details=[
                BaseExceptionDetail(
                    type=INVALID_ARGUMENT_VIOLATION_TYPE,
                    message="Default package repositories cannot be deleted.",
                )
            ]
        )

    async def test_delete_default_package_repository(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.package_repositories = Mock(PackageRepositoriesService)
        services_mock.package_repositories.delete_by_id.side_effect = BadRequestException(
            details=[
                BaseExceptionDetail(
                    type=CANNOT_DELETE_DEFAULT_PACKAGE_REPO_VIOLATION_TYPE,
                    message="Default package repositories cannot be deleted.",
                )
            ]
        )
        response = await mocked_api_client_admin.delete(f"{self.BASE_PATH}/1")

        error_response = ErrorBodyResponse(**response.json())
        assert response.status_code == 400
        assert error_response.code == 400
        assert error_response.message == "Bad request."
        assert (
            error_response.details[0].type
            == CANNOT_DELETE_DEFAULT_PACKAGE_REPO_VIOLATION_TYPE
        )

    async def test_delete_resource(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.package_repositories = Mock(PackageRepositoriesService)
        services_mock.package_repositories.delete_by_id.side_effect = None
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/100"
        )
        assert response.status_code == 204

    async def test_delete_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.package_repositories = Mock(PackageRepositoriesService)
        services_mock.package_repositories.delete_by_id.side_effect = [
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
