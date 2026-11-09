# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path
import typing
from unittest.mock import Mock

import pytest

from maasserver.testing.openfga import OpenFGAClientMock
from maasservicelayer.services import ServiceCollectionV3


def get_test_data_file(filename: str) -> str:
    test_data_path = Path(__file__).parent / "test_data" / filename
    with open(test_data_path, "r") as f:
        return f.read()


class ContextManagerMock:
    def __init__(self, mock):
        self.mock = mock

    def __enter__(self):
        return self.mock

    def __exit__(self, exc_type, exc, tb):
        pass


class AsyncContextManagerMock:
    """Mock for async context managers with nested mocking capabilities."""

    def __init__(self, mock):
        """Initialize with a mock that will be returned from __aenter__."""
        self.mock = mock

    async def __aenter__(self):
        """Enter async context manager."""
        return self.mock

    async def __aexit__(self, exc_type, exc, tb):
        """Exit async context manager."""
        pass

    def request(self, *args, **kwargs):
        """Return mock to support chaining."""
        return self.mock


class AsyncIteratorMock:
    """Mock for async iterators."""

    def __init__(self, iterable) -> None:
        self.iterable = iterable

    def __aiter__(self):
        return self

    async def __anext__(self):
        if len(self.iterable) > 0:
            return self.iterable.pop(0)
        else:
            raise StopAsyncIteration


def create_services_mock() -> Mock:
    services_mock = Mock(ServiceCollectionV3)
    for (
        service_name,
        service_class,
    ) in typing.get_type_hints(ServiceCollectionV3).items():
        setattr(services_mock, service_name, Mock(spec_set=service_class))
    return services_mock


@pytest.fixture
def services_mock():
    yield create_services_mock()


@pytest.fixture
def mock_openfga(mocker):
    openfga_mock = OpenFGAClientMock()
    mocker.patch("maasserver.openfga._get_client", return_value=openfga_mock)
    yield
