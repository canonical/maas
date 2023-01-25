# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Performance testing related classes and functions for MAAS and its applications"""


from contextlib import contextmanager, ExitStack
from cProfile import Profile
import gc
import json
import os
from pathlib import Path
import time
import tracemalloc
from typing import Any

import pytest

from maastesting.fixtures import MAASDataFixture, MAASRootFixture

DEFAULT_BRANCH = "master"


@pytest.fixture(scope="session")
def maas_root():
    if "MAAS_ROOT" in os.environ:
        return MAASRootFixture()
    return None


@pytest.fixture(scope="session")
def maas_data():
    if "MAAS_DATA" in os.environ:
        return MAASDataFixture()
    return None


# registry for tracers
PERF_TRACERS = {}


def pytest_addoption(parser):
    parser.addoption(
        "--perf-output-dir",
        help="The directory where to output performance measurements.",
    )
    parser.addoption(
        "--perf-tracers",
        nargs="+",
        choices=sorted(PERF_TRACERS),
        default=["timing", "queries"],
        help="Performance features to enable.",
    )


@pytest.fixture(scope="session")
def perf(pytestconfig, request):
    # mark all tests so that the database is re-created after each one
    request.applymarker(pytest.mark.recreate_db)

    outdir = pytestconfig.getoption("--perf-output-dir")
    tracers = pytestconfig.getoption("--perf-tracers")
    perf_tester = PerfTester(
        os.environ.get("GIT_BRANCH"),
        os.environ.get("GIT_HASH"),
        outdir=outdir,
        tracers=tracers,
    )
    yield perf_tester
    perf_tester.write_results()


def perf_tracer(cls):
    """Decorator to register test features."""
    PERF_TRACERS[cls.name] = cls
    return cls


class PerfTracer:
    """A profiling tracer that can be enabled during tests."""

    name = ""

    def __init__(self, test_name):
        self.test_name = test_name

    @property
    def dump_file_name(self) -> str:
        """Name of the dump file."""
        return f"{self.test_name}.{self.name}"

    def dump_results(self, file_path: Path):
        """Dump test results to file."""
        pass

    def results(self) -> dict[str, Any]:
        """Return a dict with profiler results."""
        return {}


@perf_tracer
class Timing(PerfTracer):
    name = "timing"

    _start = None
    _duration = None

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        end = time.monotonic()
        self._duration = end - self._start

    def results(self):
        return {"duration": self._duration}


@perf_tracer
class QueryCounter(PerfTracer):
    name = "queries"

    _count = 0
    _time = 0.0

    def __init__(self, test_name):
        super().__init__(test_name)
        self._sqlalchemy_counter = SQLAlchemyQueryCounter()

    def __enter__(self):
        from django.db import reset_queries

        reset_queries()
        self._sqlalchemy_counter.install()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return

        from django.db import connection

        self._count = len(connection.queries)
        self._time = float(
            sum((float(entry["time"]) for entry in connection.queries))
        )
        self._count += self._sqlalchemy_counter.count
        self._time += self._sqlalchemy_counter.time
        self._add_psycopg_counters(connection)
        self._sqlalchemy_counter.remove()

    def _add_psycopg_counters(self, connection):
        track = getattr(connection, "_psycopg_track", None)
        if not track:
            return
        self._count += track["count"]
        self._time += track["time"]

    def results(self):
        return {"query_count": self._count, "query_time": self._time}


class SQLAlchemyQueryCounter:

    count = 0
    time = 0.0

    def before_cursor_execute(
        self, conn, cursor, statement, parameters, context, executemany
    ):
        conn.info.setdefault("query_start_time", []).append(
            time.perf_counter()
        )

    def after_cursor_execute(
        self, conn, cursor, statement, parameters, context, executemany
    ):
        query_time = time.perf_counter() - conn.info["query_start_time"].pop(
            -1
        )
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


@perf_tracer
class MemoryTracer(PerfTracer):
    name = "memory"

    _snapshot = None

    def __enter__(self):
        tracemalloc.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return

        self._snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

    def results(self):
        stats = self._snapshot.statistics("lineno")
        return {"memory": sum(stat.size for stat in stats)}

    def dump_results(self, file_path: Path):
        self._snapshot.dump(str(file_path))


@perf_tracer
class Profiler(PerfTracer):
    """Produces profiling info for tests

    This functions uses cProfile module to provide deterministic profiling data
    for tests. The overhead is reasonable, typically < 5%.
    """

    name = "profile"

    _profiler = None

    def __enter__(self):
        self._profiler = Profile()
        self._profiler.enable()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._profiler.disable()

    def dump_results(self, file_path: Path):
        self._profiler.dump_stats(file_path)


class PerfTester:
    """PerfTester is responsible for recording performance tests"""

    def __init__(
        self,
        git_branch=None,
        git_hash=None,
        outdir=None,
        tracers=(),
    ):
        self.outdir = outdir
        if self.outdir is not None:
            self.outdir = Path(self.outdir)
        self.tracers = tracers
        self.results = {"branch": git_branch, "commit": git_hash, "tests": {}}

    @contextmanager
    def record(self, name):
        tracers = []
        # Collect all the garbage before tracers begin, so that collection of
        # unrelated garbage won't affect measurements.
        gc.collect()
        with ExitStack() as stack:
            for tracer in self.tracers:
                tracer_class = PERF_TRACERS[tracer]
                tracers.append(stack.enter_context(tracer_class(name)))
            yield
            # Collect the garbage that was created by the code that is being
            # profiled, so that we get a more consistent measurements.
            # Otherwise, a small change to the code under test could cause a
            # big change in measurements due to a new garbage collection being
            # triggered.
            gc.collect()

        if self.outdir:
            self.outdir.mkdir(parents=True, exist_ok=True)
        results = {}
        for tracer in tracers:
            results.update(tracer.results())
            if self.outdir:
                tracer.dump_results(self.outdir / tracer.dump_file_name)
        self.results["tests"][name] = results

    def write_results(self):
        if self.outdir:
            outfile = self.outdir / "results.json"
            outfile.write_text(json.dumps(self.results))
        else:
            print("\n" + json.dumps(self.results, sort_keys=True, indent=4))
