import asyncio
from collections import defaultdict
from unittest.mock import Mock

import pytest
from temporalio.api.workflowservice.v1 import (
    DescribeNamespaceResponse,
    RegisterNamespaceResponse,
)


@pytest.fixture
def mock_register_namespace_response():
    future = asyncio.Future()
    future.set_result(RegisterNamespaceResponse())
    return future


@pytest.fixture
def mock_describe_namespace_response():
    future = asyncio.Future()
    future.set_result(DescribeNamespaceResponse())
    return future


@pytest.fixture
def mock_workflow_handle():
    handle = Mock()
    return handle


@pytest.fixture
def mock_temporal_client(
    mock_register_namespace_response,
    mock_describe_namespace_response,
    mock_workflow_handle,
):
    client = Mock()
    client.config = lambda: defaultdict(list)
    client.service_client.workflow_service.register_namespace = (
        lambda _: mock_register_namespace_response
    )
    client.service_client.workflow_service.describe_namespace = (
        lambda _: mock_describe_namespace_response
    )
    workflow_handle_future = asyncio.Future()
    workflow_handle_future.set_result = mock_workflow_handle
    client.get_workflow_handle = lambda _: workflow_handle_future
    return client


@pytest.fixture
def mock_temporal_connect(mocker, mock_temporal_client):
    return mocker.patch(
        "temporalio.client.Client.connect", return_value=mock_temporal_client
    )
