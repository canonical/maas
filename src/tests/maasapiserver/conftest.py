import pytest

from .fixtures.app import (
    api_app,
    api_client,
    authenticated_api_client,
    authenticated_user,
    user_session_id,
)
from .fixtures.db import (
    db,
    db_connection,
    fixture,
    test_config,
    transaction_middleware_class,
)

__all__ = [
    "api_app",
    "api_client",
    "authenticated_api_client",
    "authenticated_user",
    "test_config",
    "db",
    "db_connection",
    "fixture",
    "transaction_middleware_class",
    "user_session_id",
]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--sqlalchemy-debug",
        help="print out SQLALchemy queries",
        action="store_true",
        default=False,
    )
