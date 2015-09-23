# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for testing database locks and related."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "lock_held_in_other_thread",
]

from contextlib import contextmanager
import threading

from maasserver.utils.orm import transactional


@contextmanager
def lock_held_in_other_thread(lock, timeout=10):
    """Hold `lock` in another thread."""
    held = threading.Event()
    done = threading.Event()

    @transactional
    def hold():
        with lock:
            held.set()
            done.wait(timeout)

    thread = threading.Thread(target=hold)
    thread.start()

    held.wait(timeout)
    try:
        yield
    finally:
        done.set()
        thread.join()
