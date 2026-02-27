# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import functools
import threading
from typing import Any, Dict

from maascommon.openfga.sync_client import SyncOpenFGAClient


class ThreadLocalFGACache:
    def __init__(self, client: SyncOpenFGAClient):
        self._client = client
        self._local = threading.local()

    @property
    def _cache(self) -> Dict[tuple, Any]:
        """Initialize the cache dict on the local storage if it doesn't exist"""
        if not hasattr(self._local, "cache"):
            self._local.cache = {}
        return self._local.cache

    def clear_cache(self):
        """Clears the cache for the current thread."""
        self._cache.clear()

    def __getattr__(self, name: str):
        """
        Fallback for any method not defined on this class.
        It looks up the attribute on the original client and wraps it.
        """
        attr = getattr(self._client, name)

        if callable(attr):

            @functools.wraps(attr)
            def wrapper(*args, **kwargs):
                # Cache key based on method name and arguments
                cache_key = (name, args, tuple(sorted(kwargs.items())))

                if cache_key not in self._cache:
                    self._cache[cache_key] = attr(*args, **kwargs)

                return self._cache[cache_key]

            return wrapper

        return attr


def _get_client():
    raw_client = SyncOpenFGAClient()
    return ThreadLocalFGACache(raw_client)


@functools.lru_cache(maxsize=1)
def get_openfga_client():
    return _get_client()
