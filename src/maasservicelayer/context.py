#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import time
from typing import Callable
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncConnection


class Context:
    def __init__(
        self,
        context_id: str | None = None,
        connection: AsyncConnection | None = None,
    ):
        self.context_id = context_id or self._generate_context_id()
        self._start_timestamp = time.time()
        self._end_timestamp = None
        self._connection = connection
        # A placeholder ATM. This is the place where all the services can append the post commits hooks to be executed after
        # the transaction has been committed.
        self._post_commit_hooks = []

    def set_connection(self, connection: AsyncConnection):
        self._connection = connection

    def get_connection(self) -> AsyncConnection:
        if not self._connection:
            raise RuntimeError(
                "There is no database connection in this context. This is likely to be a programming error, "
                "please open a bug with the stacktrace"
            )
        return self._connection

    def get_post_commit_hooks(self) -> list[Callable]:
        return self._post_commit_hooks

    def add_post_commit_hook(self, callable: Callable) -> None:
        self._post_commit_hooks.append(callable)

    def get_elapsed_time_seconds(self) -> float:
        return time.time() - self._start_timestamp

    def _generate_context_id(self) -> str:
        return str(uuid4())
