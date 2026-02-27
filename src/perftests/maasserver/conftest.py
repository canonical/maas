# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasserver.openfga import get_openfga_client
from tests.e2e.conftest import (
    mock_maas_env,
    openfga_server,
    openfga_socket_path,
    project_root_path,
)
from tests.maasapiserver.fixtures.db import db, test_config

__all__ = [
    "db",
    "test_config",
    "openfga_socket_path",
    "openfga_server",
    "mock_maas_env",
    "project_root_path",
]


@pytest.fixture(autouse=True)
def clear_openfga_client_cache():
    # Clear the cache of the get_openfga_client function before each test to ensure a fresh client instance is used.
    get_openfga_client.cache_clear()
