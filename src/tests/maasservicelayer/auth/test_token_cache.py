# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import OrderedDict

import pytest

from maasservicelayer.auth.token_cache import AccessTokenValidationCache
from maasservicelayer.utils.date import utcnow


@pytest.fixture
def empty_cache() -> AccessTokenValidationCache:
    return AccessTokenValidationCache(
        max_size=3,
        ttl_seconds=2,
    )


@pytest.fixture
def cache_with_items() -> AccessTokenValidationCache:
    now = utcnow().timestamp()
    cache = AccessTokenValidationCache(
        max_size=3,
        ttl_seconds=2,
    )
    cache._cache = OrderedDict(
        {"token1": now + 1000, "token2": now - 100, "token3": now + 500}
    )
    return cache


class TestAccessTokenValidationCache:
    async def test_is_valid_token(
        self, cache_with_items: AccessTokenValidationCache
    ) -> None:
        is_valid = await cache_with_items.is_valid("token1")
        assert is_valid is True
        assert list(cache_with_items._cache.keys())[-1] == "token1"

    async def test_is_valid_expired_token(
        self, cache_with_items: AccessTokenValidationCache
    ) -> None:
        is_valid = await cache_with_items.is_valid("token2")
        assert is_valid is False
        assert "token2" not in cache_with_items._cache

    async def test_is_valid_missing_token(
        self, cache_with_items: AccessTokenValidationCache
    ) -> None:
        is_valid = await cache_with_items.is_valid("missing_token")
        assert is_valid is False

    async def test_add_token_no_eviction(
        self, empty_cache: AccessTokenValidationCache
    ) -> None:
        await empty_cache.add("token1")

        assert len(empty_cache._cache) == 1
        assert "token1" in empty_cache._cache

    async def test_add_token_eviction(
        self, cache_with_items: AccessTokenValidationCache
    ) -> None:
        await cache_with_items.add("token4")

        assert len(cache_with_items._cache) == 3
        assert "token2" in cache_with_items._cache
        assert "token3" in cache_with_items._cache
        assert "token4" in cache_with_items._cache
        assert "token1" not in cache_with_items._cache

    async def test_remove_token(
        self, cache_with_items: AccessTokenValidationCache
    ) -> None:
        await cache_with_items.remove("token3")

        assert len(cache_with_items._cache) == 2
        assert "token3" not in cache_with_items._cache
