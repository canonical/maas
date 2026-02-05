# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from collections import OrderedDict

from maasservicelayer.utils.date import utcnow


class AccessTokenValidationCache:
    """
    An in-memory cache for validated OAuth access tokens.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 180):
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._lock = asyncio.Lock()

    async def is_valid(self, token: str) -> bool:
        async with self._lock:
            now = utcnow().timestamp()
            expiration = self._cache.get(token)
            if expiration is None:
                return False
            if expiration < now:
                self._cache.pop(token, None)
                return False
            self._cache.move_to_end(token)
            return True

    async def add(self, token: str) -> None:
        async with self._lock:
            now = utcnow().timestamp()
            expiration = now + self._ttl_seconds
            self._cache[token] = expiration
            self._cache.move_to_end(token)
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    async def remove(self, token: str) -> None:
        async with self._lock:
            self._cache.pop(token, None)
