# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_BOOT_RESOURCE_1 = BootResource(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    rtype=BootResourceType.SYNCED,
    name="custom/image-noble",
    architecture="amd64/generic",
    extra={},
    kflavor=None,
    bootloader_type=None,
    rolling=False,
    base_image="ubuntu/noble",
    alias=None,
    last_deployed=None,
)


class TestBootResourcesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/boot_resources"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return []

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

    async def test_delete_boot_resources_204(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id.return_value = (
            TEST_BOOT_RESOURCE_1
        )
        services_mock.boot_resources.delete_by_id.return_value = (
            TEST_BOOT_RESOURCE_1
        )

        response = await mocked_api_client_admin.delete(f"{self.BASE_PATH}/1")

        assert response.status_code == 204

        services_mock.boot_resources.delete_by_id.assert_called_once_with(
            id=1,
            etag_if_match=None,
        )

    async def test_delete_boot_resources_204_by_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        correct_etag = "correct_etag"

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id.return_value = (
            TEST_BOOT_RESOURCE_1
        )
        services_mock.boot_resources.delete_by_id.return_value = (
            TEST_BOOT_RESOURCE_1
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/1",
            headers={"if-match": correct_etag},
        )

        assert response.status_code == 204

        services_mock.boot_resources.delete_by_id.assert_called_once_with(
            id=1,
            etag_if_match=correct_etag,
        )

    async def test_delete_boot_resources_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id.return_value = None
        services_mock.boot_resources.delete_by_id.side_effect = (
            NotFoundException()
        )

        response = await mocked_api_client_admin.delete(f"{self.BASE_PATH}/2")

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 404

        services_mock.boot_resources.delete_by_id.assert_called_once_with(
            id=2,
            etag_if_match=None,
        )

    async def test_delete_boot_resources_412_wrong_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        wrong_etag = "wrong_etag"
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id.return_value = (
            TEST_BOOT_RESOURCE_1
        )
        services_mock.boot_resources.delete_by_id.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=ETAG_PRECONDITION_VIOLATION_TYPE,
                    message=f"The resource etag '{wrong_etag}' did not match 'my_etag'.",
                )
            ]
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/2",
            headers={"if-match": wrong_etag},
        )

        assert response.status_code == 412

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.code == 412
        assert error_response.message == "A precondition has failed."
        assert (
            error_response.details[0].type == ETAG_PRECONDITION_VIOLATION_TYPE  # pyright: ignore[reportOptionalSubscript]
        )

        services_mock.boot_resources.delete_by_id.assert_called_once_with(
            id=2,
            etag_if_match=wrong_etag,
        )
