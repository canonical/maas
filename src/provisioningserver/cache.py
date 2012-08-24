# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API credentials for node-group workers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'cache',
    'initialize',
    ]


from multiprocessing import Manager


class Cache(object):
    """A process-safe dict-like cache."""

    def __init__(self, cache_backend):
        self.cache_backend = cache_backend

    def set(self, key, value):
        self.cache_backend[key] = value

    def get(self, key):
        return self.cache_backend.get(key, None)

    def clear(self):
        self.cache_backend.clear()


_manager = None

cache = None

initialized = False


def initialize():
    """Initialize cache of shared data between processes.

    This needs to be done exactly once, by the parent process, before it
    start forking off workers.
    """
    global _manager
    global cache
    global initialized
    if not initialized:
        _manager = Manager()
        cache = Cache(_manager.dict())
        initialized = True
