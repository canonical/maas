#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.operations import (
    OperationResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.models.operations import Operation
from maasservicelayer.utils.date import utcnow


class TestOperationResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        operation = Operation(
            id=1,
            uuid="test-uuid",
            op_type=OperationType.MACHINE_DEPLOY,
            resource_id=42,
            resource_type="machine",
            status=OperationStatus.RUNNING,
            created=now,
            updated=now,
            started=now,
            finished=None,
            current_task="deploy-task",
            parameters={"key": "value"},
            result_errors=None,
            is_bulk=False,
            parent_id=None,
            user_id=1,
        )
        response = OperationResponse.from_model(
            operation=operation,
            self_base_hyperlink=f"{V3_API_PREFIX}/operations",
        )
        assert response.uuid == operation.uuid
        assert response.op_type == operation.op_type
        assert response.resource_id == operation.resource_id
        assert response.resource_type == operation.resource_type
        assert response.status == operation.status
        assert response.created == operation.created
        assert response.updated == operation.updated
        assert response.started == operation.started
        assert response.finished == operation.finished
        assert response.current_task == operation.current_task
        assert response.parameters == operation.parameters
        assert response.result_errors == operation.result_errors
        assert response.is_bulk == operation.is_bulk
        assert response.parent_id == operation.parent_id
        assert response.user_id == operation.user_id
        assert response.kind == "Operation"

    def test_hal_links(self) -> None:
        now = utcnow()
        operation = Operation(
            id=1,
            uuid="test-uuid",
            op_type=OperationType.MACHINE_DEPLOY,
            status=OperationStatus.ACCEPTED,
            created=now,
            updated=now,
            is_bulk=False,
            user_id=1,
        )
        base_link = f"{V3_API_PREFIX}/operations"
        response = OperationResponse.from_model(
            operation=operation,
            self_base_hyperlink=base_link,
        )
        assert response.hal_links.self.href == f"{base_link}/test-uuid"

    def test_hal_links_strips_trailing_slash(self) -> None:
        now = utcnow()
        operation = Operation(
            id=1,
            uuid="test-uuid",
            op_type=OperationType.MACHINE_DEPLOY,
            status=OperationStatus.ACCEPTED,
            created=now,
            updated=now,
            is_bulk=False,
            user_id=1,
        )
        base_link = f"{V3_API_PREFIX}/operations/"
        response = OperationResponse.from_model(
            operation=operation,
            self_base_hyperlink=base_link,
        )
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/operations/test-uuid"
        )

    def test_from_model_optional_fields_none(self) -> None:
        now = utcnow()
        operation = Operation(
            id=1,
            uuid="test-uuid",
            op_type=OperationType.MACHINE_COMMISSION,
            status=OperationStatus.ACCEPTED,
            created=now,
            updated=now,
            is_bulk=True,
        )
        response = OperationResponse.from_model(
            operation=operation,
            self_base_hyperlink=f"{V3_API_PREFIX}/operations",
        )
        assert response.resource_id is None
        assert response.resource_type is None
        assert response.started is None
        assert response.finished is None
        assert response.current_task is None
        assert response.parameters is None
        assert response.result_errors is None
        assert response.parent_id is None
        assert response.user_id is None

    def test_from_model_with_result_errors(self) -> None:
        now = utcnow()
        operation = Operation(
            id=1,
            uuid="test-uuid",
            op_type=OperationType.MACHINE_DEPLOY,
            status=OperationStatus.FAILED,
            created=now,
            updated=now,
            is_bulk=False,
            result_errors={"error": "something went wrong"},
            user_id=1,
        )
        response = OperationResponse.from_model(
            operation=operation,
            self_base_hyperlink=f"{V3_API_PREFIX}/operations",
        )
        assert response.result_errors == {"error": "something went wrong"}
