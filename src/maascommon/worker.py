# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Utilities for the regiond workers.
"""

import os

from maascommon.http import REGIOND_SOCKET_PATH

MAX_WORKERS_COUNT = int(
    os.environ.get("MAAS_REGIOND_WORKER_COUNT", os.cpu_count())  # pyright: ignore [reportArgumentType]
)


def set_max_workers_count(worker_count: int):
    """Set the global `MAX_WORKERS_COUNT`."""
    global MAX_WORKERS_COUNT
    MAX_WORKERS_COUNT = worker_count


def get_worker_ids() -> list[str]:
    return [str(worker_id) for worker_id in range(MAX_WORKERS_COUNT)]


def build_unix_socket_path_for_worker(worker_id: str) -> str:
    return f"{REGIOND_SOCKET_PATH}.{worker_id}"


def worker_socket_paths() -> list[str]:
    return [
        build_unix_socket_path_for_worker(worker_id)
        for worker_id in get_worker_ids()
    ]
