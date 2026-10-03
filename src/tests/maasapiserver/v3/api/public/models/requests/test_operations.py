#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.operations import (
    OperationFilterParams,
)
from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.db.repositories.operations import OperationsClauseFactory
from maasservicelayer.exceptions.catalog import ValidationException


class TestOperationFilterParams:
    @pytest.mark.parametrize(
        "status,op_type,is_bulk,expected_status,expected_op_type,expected_is_bulk",
        [
            (
                OperationStatus.RUNNING,
                OperationType.MACHINE_DEPLOY,
                True,
                OperationStatus.RUNNING,
                OperationType.MACHINE_DEPLOY,
                True,
            ),
            (
                OperationStatus.FAILED,
                OperationType.MACHINE_COMMISSION,
                False,
                OperationStatus.FAILED,
                OperationType.MACHINE_COMMISSION,
                False,
            ),
        ],
    )
    def test_field_values(
        self,
        status: OperationStatus,
        op_type: OperationType,
        is_bulk: bool,
        expected_status: OperationStatus,
        expected_op_type: OperationType,
        expected_is_bulk: bool,
    ) -> None:
        params = OperationFilterParams(
            status=status, op_type=op_type, is_bulk=is_bulk
        )
        assert params.status == expected_status
        assert params.op_type == expected_op_type
        assert params.is_bulk == expected_is_bulk

    @pytest.mark.parametrize(
        "status",
        [
            OperationStatus.ACCEPTED,
            OperationStatus.RUNNING,
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
            OperationStatus.CANCELLING,
            OperationStatus.CANCELLED,
            OperationStatus.COMPLETED_WITH_ERRORS,
        ],
    )
    def test_valid_status_values(self, status: OperationStatus) -> None:
        params = OperationFilterParams(
            status=status, op_type=None, is_bulk=None
        )
        assert params.status == status

    @pytest.mark.parametrize(
        "op_type",
        [
            OperationType.MACHINE_COMMISSION,
            OperationType.MACHINE_DEPLOY,
            OperationType.MACHINE_BULKDEPLOY,
            OperationType.SELECTION_SYNC,
        ],
    )
    def test_valid_op_type_values(self, op_type: OperationType) -> None:
        params = OperationFilterParams(
            status=None, op_type=op_type, is_bulk=None
        )
        assert params.op_type == op_type

    def test_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            OperationFilterParams(
                status="INVALID_STATUS", op_type=None, is_bulk=None
            )

    def test_invalid_op_type(self) -> None:
        with pytest.raises(ValidationError):
            OperationFilterParams(
                status=None, op_type="invalid.type", is_bulk=None
            )

    def test_invalid_is_bulk(self) -> None:
        with pytest.raises(ValidationError):
            OperationFilterParams(
                status=None, op_type=None, is_bulk="not_a_bool"
            )

    @pytest.mark.parametrize(
        "resource_type,resource_id",
        [
            ("machine", 42),
            ("machine", None),
        ],
    )
    def test_resource_field_values(
        self, resource_type: str | None, resource_id: int | None
    ) -> None:
        params = OperationFilterParams(
            resource_type=resource_type, resource_id=resource_id
        )
        assert params.resource_type == resource_type
        assert params.resource_id == resource_id

    def test_invalid_resource_id(self) -> None:
        with pytest.raises(ValidationError):
            OperationFilterParams(
                resource_type="machine", resource_id="not_an_int"
            )

    def test_resource_id_requires_resource_type(self) -> None:
        with pytest.raises(ValidationException) as exc_info:
            OperationFilterParams(resource_type=None, resource_id=42)
        assert exc_info.value.details is not None
        assert exc_info.value.details[0].field == "resource_type"

    @pytest.mark.parametrize(
        "status,op_type,is_bulk,resource_type,resource_id,expected",
        [
            (
                OperationStatus.RUNNING,
                None,
                None,
                None,
                None,
                OperationsClauseFactory.with_status(OperationStatus.RUNNING),
            ),
            (
                None,
                OperationType.MACHINE_DEPLOY,
                None,
                None,
                None,
                OperationsClauseFactory.with_op_type(
                    OperationType.MACHINE_DEPLOY
                ),
            ),
            (
                None,
                None,
                True,
                None,
                None,
                OperationsClauseFactory.with_is_bulk(True),
            ),
            (
                None,
                None,
                False,
                None,
                None,
                OperationsClauseFactory.with_is_bulk(False),
            ),
            (
                None,
                None,
                None,
                "machine",
                None,
                OperationsClauseFactory.with_resource_type("machine"),
            ),
            (
                None,
                None,
                None,
                "machine",
                42,
                OperationsClauseFactory.and_clauses(
                    [
                        OperationsClauseFactory.with_resource_type("machine"),
                        OperationsClauseFactory.with_resource_id(42),
                    ]
                ),
            ),
            (
                OperationStatus.RUNNING,
                OperationType.MACHINE_DEPLOY,
                True,
                None,
                None,
                OperationsClauseFactory.and_clauses(
                    [
                        OperationsClauseFactory.with_status(
                            OperationStatus.RUNNING
                        ),
                        OperationsClauseFactory.with_op_type(
                            OperationType.MACHINE_DEPLOY
                        ),
                        OperationsClauseFactory.with_is_bulk(True),
                    ]
                ),
            ),
            (
                None,
                OperationType.MACHINE_COMMISSION,
                None,
                "machine",
                42,
                OperationsClauseFactory.and_clauses(
                    [
                        OperationsClauseFactory.with_op_type(
                            OperationType.MACHINE_COMMISSION
                        ),
                        OperationsClauseFactory.with_resource_type("machine"),
                        OperationsClauseFactory.with_resource_id(42),
                    ]
                ),
            ),
        ],
    )
    def test_to_clause(
        self, status, op_type, is_bulk, resource_type, resource_id, expected
    ) -> None:
        params = OperationFilterParams(
            status=status,
            op_type=op_type,
            is_bulk=is_bulk,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        clause = params.to_clause()
        assert clause is not None
        assert clause == expected

    @pytest.mark.parametrize(
        "status,op_type,is_bulk,resource_type,resource_id,expected",
        [
            (
                OperationStatus.RUNNING,
                None,
                None,
                None,
                None,
                "status=RUNNING",
            ),
            (
                None,
                OperationType.MACHINE_DEPLOY,
                None,
                None,
                None,
                "op_type=machine.deploy",
            ),
            (
                None,
                None,
                True,
                None,
                None,
                "is_bulk=true",
            ),
            (
                None,
                None,
                False,
                None,
                None,
                "is_bulk=false",
            ),
            (
                None,
                None,
                None,
                "machine",
                None,
                "resource_type=machine",
            ),
            (
                None,
                None,
                None,
                "machine",
                42,
                "resource_type=machine&resource_id=42",
            ),
            (
                OperationStatus.RUNNING,
                OperationType.MACHINE_DEPLOY,
                True,
                None,
                None,
                "status=RUNNING&op_type=machine.deploy&is_bulk=true",
            ),
            (
                None,
                OperationType.MACHINE_COMMISSION,
                None,
                "machine",
                42,
                "op_type=machine.commission&resource_type=machine"
                "&resource_id=42",
            ),
        ],
    )
    def test_to_href_format(
        self, status, op_type, is_bulk, resource_type, resource_id, expected
    ) -> None:
        params = OperationFilterParams(
            status=status,
            op_type=op_type,
            is_bulk=is_bulk,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        assert params.to_href_format() == expected

    def test_to_href_format_encodes_resource_type(self) -> None:
        params = OperationFilterParams(
            status=None,
            op_type=None,
            is_bulk=None,
            resource_type="machine&bootresource",
            resource_id=None,
        )
        assert (
            params.to_href_format() == "resource_type=machine%26bootresource"
        )
