# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from time import perf_counter


class SQLAlchemyQueryCounter:
    count = 0
    time = 0.0

    def before_cursor_execute(
        self, conn, cursor, statement, parameters, context, executemany
    ):
        conn.info.setdefault("query_start_time", []).append(perf_counter())

    def after_cursor_execute(
        self, conn, cursor, statement, parameters, context, executemany
    ):
        query_time = perf_counter() - conn.info["query_start_time"].pop(-1)
        self.count += 1
        self.time += query_time

    def install(self):
        from sqlalchemy.engine import Engine
        from sqlalchemy.event import listen

        listen(Engine, "before_cursor_execute", self.before_cursor_execute)
        listen(Engine, "after_cursor_execute", self.after_cursor_execute)
        return self

    def remove(self):
        from sqlalchemy.engine import Engine
        from sqlalchemy.event import remove

        remove(Engine, "before_cursor_execute", self.before_cursor_execute)
        remove(Engine, "after_cursor_execute", self.after_cursor_execute)
        self.count = 0
        self.time = 0.0
