# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Callable
from unittest.mock import AsyncMock, Mock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.responses.operations import (
    OperationResponse,
    OperationsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.operations import OperationsClauseFactory
from maasservicelayer.exceptions.catalog import (
    ConflictException,
    NotFoundException,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.operations import Operation
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.operations import OperationsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_OPERATION = Operation(
    id=1,
    uuid="test-uuid-1",
    op_type=OperationType.MACHINE_DEPLOY,
    status=OperationStatus.RUNNING,
    is_bulk=False,
    created=utcnow(),
    updated=utcnow(),
)

TEST_OPERATION_2 = Operation(
    id=2,
    uuid="test-uuid-2",
    op_type=OperationType.MACHINE_COMMISSION,
    status=OperationStatus.ACCEPTED,
    is_bulk=True,
    created=utcnow(),
    updated=utcnow(),
)


def _setup_openfga_mock(services_mock: ServiceCollectionV3) -> AsyncMock:
    openfga_client = Mock()
    openfga_client.can_view_operations = AsyncMock(return_value=True)
    openfga_client.can_edit_operations = AsyncMock(return_value=True)
    services_mock.openfga_tuples.get_client.return_value = openfga_client
    return openfga_client


class TestOperationsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/operations"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return []

    @pytest.fixture
    def endpoints_with_authentication_only(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=self.BASE_PATH,
            ),
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/{TEST_OPERATION.uuid}",
            ),
            Endpoint(
                method="DELETE",
                path=f"{self.BASE_PATH}/{TEST_OPERATION.uuid}",
            ),
        ]

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions()
        openfga_client = _setup_openfga_mock(services_mock)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.list_for_user.return_value = ListResult(
            items=[TEST_OPERATION, TEST_OPERATION_2], total=2
        )

        response = await client.get(f"{self.BASE_PATH}?size=2")
        operations_response = OperationsListResponse(**response.json())
        assert response.status_code == 200
        assert len(operations_response.items) == 2
        assert operations_response.total == 2
        assert operations_response.next is None
        openfga_client.can_view_operations.assert_awaited_once()
        services_mock.operations.list_for_user.assert_called_once_with(
            1,
            2,
            user_id=0,
            can_view_all=True,
            query=QuerySpec(where=None),
        )

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions()
        _setup_openfga_mock(services_mock)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.list_for_user.return_value = ListResult(
            items=[TEST_OPERATION], total=2
        )

        response = await client.get(f"{self.BASE_PATH}?size=1")
        operations_response = OperationsListResponse(**response.json())
        assert response.status_code == 200
        assert len(operations_response.items) == 1
        assert operations_response.next == f"{self.BASE_PATH}?page=2&size=1"
        services_mock.operations.list_for_user.assert_called_once_with(
            1,
            1,
            user_id=0,
            can_view_all=True,
            query=QuerySpec(where=None),
        )

    async def test_list_operations_filter_by_status(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions()
        _setup_openfga_mock(services_mock)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.list_for_user.return_value = ListResult(
            items=[TEST_OPERATION], total=1
        )

        response = await client.get(
            f"{self.BASE_PATH}?status={OperationStatus.RUNNING.value}"
        )
        operations_response = OperationsListResponse(**response.json())
        assert response.status_code == 200
        assert len(operations_response.items) == 1
        assert operations_response.items[0].status == OperationStatus.RUNNING
        services_mock.operations.list_for_user.assert_called_once_with(
            1,
            20,
            user_id=0,
            can_view_all=True,
            query=QuerySpec(
                where=OperationsClauseFactory.with_status(
                    OperationStatus.RUNNING
                )
            ),
        )

    async def test_get_operation(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions()
        _setup_openfga_mock(services_mock)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.get_by_uuid_for_user.return_value = (
            TEST_OPERATION
        )

        response = await client.get(f"{self.BASE_PATH}/{TEST_OPERATION.uuid}")
        operation_response = OperationResponse(**response.json())
        assert response.status_code == 200
        assert operation_response.uuid == TEST_OPERATION.uuid
        assert operation_response.op_type == TEST_OPERATION.op_type
        services_mock.operations.get_by_uuid_for_user.assert_called_once_with(
            TEST_OPERATION.uuid, user_id=0, can_view_all=True
        )

    async def test_get_operation_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions()
        _setup_openfga_mock(services_mock)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.get_by_uuid_for_user.side_effect = (
            NotFoundException()
        )

        response = await client.get(f"{self.BASE_PATH}/non-existent-uuid")
        assert response.status_code == 404

    async def test_cancel_operation(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions()
        _setup_openfga_mock(services_mock)
        cancelling_operation = TEST_OPERATION.model_copy(
            update={"status": OperationStatus.CANCELLING}
        )
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.cancel_for_user.return_value = (
            cancelling_operation
        )
        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.cancel_workflow_by_operation_uuid = AsyncMock()

        response = await client.delete(
            f"{self.BASE_PATH}/{TEST_OPERATION.uuid}"
        )
        operation_response = OperationResponse(**response.json())
        assert response.status_code == 202
        assert operation_response.status == OperationStatus.CANCELLING
        services_mock.operations.cancel_for_user.assert_called_once_with(
            uuid=TEST_OPERATION.uuid,
            user_id=0,
            can_edit_all=True,
            can_view_all=True,
        )
        services_mock.temporal.cancel_workflow_by_operation_uuid.assert_awaited_once_with(
            TEST_OPERATION.uuid
        )

    async def test_cancel_operation_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions()
        _setup_openfga_mock(services_mock)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.cancel_for_user.side_effect = (
            NotFoundException()
        )

        response = await client.delete(f"{self.BASE_PATH}/nonexistent-uuid")
        assert response.status_code == 404

    async def test_cancel_operation_conflict(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions()
        _setup_openfga_mock(services_mock)
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.cancel_for_user.side_effect = (
            ConflictException()
        )

        response = await client.delete(
            f"{self.BASE_PATH}/{TEST_OPERATION.uuid}"
        )
        assert response.status_code == 409

    async def test_get_operation_forbidden_for_other_user(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions()
        openfga_client = _setup_openfga_mock(services_mock)
        openfga_client.can_view_operations.return_value = False
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.get_by_uuid_for_user.side_effect = (
            NotFoundException()
        )

        response = await client.get(f"{self.BASE_PATH}/{TEST_OPERATION.uuid}")
        assert response.status_code == 404

    async def test_list_operations_non_admin_with_status_filter(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions()
        openfga_client = _setup_openfga_mock(services_mock)
        openfga_client.can_view_operations.return_value = False
        services_mock.operations = Mock(OperationsService)
        services_mock.operations.list_for_user.return_value = ListResult(
            items=[TEST_OPERATION], total=1
        )

        response = await client.get(
            f"{self.BASE_PATH}?status={OperationStatus.RUNNING.value}"
        )
        operations_response = OperationsListResponse(**response.json())
        assert response.status_code == 200
        assert len(operations_response.items) == 1
        assert operations_response.items[0].status == OperationStatus.RUNNING
        openfga_client.can_view_operations.assert_awaited_once()
        services_mock.operations.list_for_user.assert_called_once_with(
            1,
            20,
            user_id=0,
            can_view_all=False,
            query=QuerySpec(
                where=OperationsClauseFactory.with_status(
                    OperationStatus.RUNNING
                )
            ),
        )
