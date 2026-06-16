# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from temporalio.api.enums.v1 import IndexedValueType
from temporalio.api.operatorservice.v1 import ListSearchAttributesResponse

from maascommon.workflows.operation import OPERATION_UUID_SEARCH_ATTRIBUTE
from maastemporalworker.temporal_script import setup_search_attributes


class TestSetupSearchAttributes:
    @pytest.mark.asyncio
    async def test_registers_missing_search_attributes(self):
        client = Mock()
        operator_service = client.service_client.operator_service
        operator_service.list_search_attributes = AsyncMock(
            return_value=ListSearchAttributesResponse()
        )
        operator_service.add_search_attributes = AsyncMock()

        await setup_search_attributes(client)

        operator_service.add_search_attributes.assert_awaited_once()
        request = operator_service.add_search_attributes.call_args.args[0]
        assert (
            request.search_attributes[OPERATION_UUID_SEARCH_ATTRIBUTE]
            == IndexedValueType.INDEXED_VALUE_TYPE_KEYWORD
        )

    @pytest.mark.asyncio
    async def test_skips_already_registered_search_attributes(self):
        client = Mock()
        operator_service = client.service_client.operator_service
        operator_service.list_search_attributes = AsyncMock(
            return_value=ListSearchAttributesResponse(
                custom_attributes={
                    OPERATION_UUID_SEARCH_ATTRIBUTE: IndexedValueType.INDEXED_VALUE_TYPE_KEYWORD
                }
            )
        )
        operator_service.add_search_attributes = AsyncMock()

        await setup_search_attributes(client)

        operator_service.add_search_attributes.assert_not_awaited()
