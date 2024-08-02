#  Copyright 2023-2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from pprint import pprint
import sys
from typing import Any, IO

from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import ClauseElement


@dataclass(init=False)
class CompiledQuery:
    """A query compiled for PostgreSQL."""

    sql: str
    params: dict[str, Any]

    def __init__(self, query: ClauseElement):
        statement = getattr(query, "statement", query)
        compiled = statement.compile(
            dialect=postgresql.dialect()  # type: ignore
        )
        self.sql = str(compiled)
        self.params = compiled.params


def print_query(query: ClauseElement, file: IO[str] = sys.stderr) -> None:
    """Print out a SQLAlchemy query, with its parameters."""
    compiled = CompiledQuery(query)
    print("---", file=file)
    print(compiled.sql, file=file)
    if compiled.params:
        print("params: ", end="", file=file)
        pprint(compiled.params, stream=file)
    print("---", file=file)
