import pytest

from .fixtures.app import api_app, api_client
from .fixtures.db import db, db_connection, fixture

__all__ = [
    "api_app",
    "api_client",
    "db",
    "db_connection",
    "fixture",
]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--sqlalchemy-debug",
        help="print out SQLALchemy queries",
        action="store_true",
        default=False,
    )
