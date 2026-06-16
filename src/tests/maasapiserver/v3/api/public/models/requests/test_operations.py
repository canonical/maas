#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.operations import (
    OperationFilterParams,
)
from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.db.repositories.operations import OperationsClauseFactory


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
        "status,op_type,is_bulk,expected",
        [
            (
                OperationStatus.RUNNING,
                None,
                None,
                OperationsClauseFactory.with_status(OperationStatus.RUNNING),
            ),
            (
                None,
                OperationType.MACHINE_DEPLOY,
                None,
                OperationsClauseFactory.with_op_type(
                    OperationType.MACHINE_DEPLOY
                ),
            ),
            (
                None,
                None,
                True,
                OperationsClauseFactory.with_is_bulk(True),
            ),
            (
                None,
                None,
                False,
                OperationsClauseFactory.with_is_bulk(False),
            ),
            (
                OperationStatus.RUNNING,
                OperationType.MACHINE_DEPLOY,
                True,
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
        ],
    )
    def test_to_clause(self, status, op_type, is_bulk, expected) -> None:
        params = OperationFilterParams(
            status=status, op_type=op_type, is_bulk=is_bulk
        )
        clause = params.to_clause()
        assert clause is not None
        assert clause == expected

    @pytest.mark.parametrize(
        "status,op_type,is_bulk,expected",
        [
            (
                OperationStatus.RUNNING,
                None,
                None,
                "status=RUNNING",
            ),
            (
                None,
                OperationType.MACHINE_DEPLOY,
                None,
                "op_type=machine.deploy",
            ),
            (
                None,
                None,
                True,
                "is_bulk=true",
            ),
            (
                None,
                None,
                False,
                "is_bulk=false",
            ),
            (
                OperationStatus.RUNNING,
                OperationType.MACHINE_DEPLOY,
                True,
                "status=RUNNING&op_type=machine.deploy&is_bulk=true",
            ),
        ],
    )
    def test_to_href_format(self, status, op_type, is_bulk, expected) -> None:
        params = OperationFilterParams(
            status=status, op_type=op_type, is_bulk=is_bulk
        )
        assert params.to_href_format() == expected
