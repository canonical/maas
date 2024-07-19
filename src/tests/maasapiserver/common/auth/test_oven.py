#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timedelta

import macaroonbakery.bakery as bakery
import pytest

from maasapiserver.common.auth.oven import AsyncOven

EPOCH = datetime(1900, 11, 17, 19, 00, 13, 0, None)
AGES = EPOCH + timedelta(days=10)


class AsyncMemoryKeyStoreStub(bakery.MemoryKeyStore):
    async def get(self, id):
        return super().get(id)

    async def root_key(self):
        return super().root_key()


@pytest.mark.asyncio
class TestAsyncOven:
    """
    Tests taken from https://git.launchpad.net/ubuntu/+source/py-macaroon-bakery/tree/macaroonbakery/tests/test_oven.py
    and adapted to the new async override
    """

    async def test_multiple_ops(self):
        memory_key_store = AsyncMemoryKeyStoreStub()
        test_oven = AsyncOven(
            root_keystore_for_ops=lambda op: memory_key_store,
            ops_store=bakery.MemoryOpsStore(),
        )
        ops = [
            bakery.Op("one", "read"),
            bakery.Op("one", "write"),
            bakery.Op("two", "read"),
        ]
        m = await test_oven.macaroon(bakery.LATEST_VERSION, AGES, None, ops)
        got_ops, conds = await test_oven.macaroon_ops([m.macaroon])
        assert len(conds) == 1  # time-before caveat.
        assert bakery.canonical_ops(got_ops) == ops

    async def test_multiple_ops_in_id(self):
        memory_key_store = AsyncMemoryKeyStoreStub()
        test_oven = AsyncOven(
            root_keystore_for_ops=lambda op: memory_key_store
        )
        ops = [
            bakery.Op("one", "read"),
            bakery.Op("one", "write"),
            bakery.Op("two", "read"),
        ]
        m = await test_oven.macaroon(bakery.LATEST_VERSION, AGES, None, ops)
        got_ops, conds = await test_oven.macaroon_ops([m.macaroon])
        assert len(conds) == 1  # time-before caveat.
        assert bakery.canonical_ops(got_ops) == ops

    async def test_multiple_ops_in_id_with_version1(self):
        memory_key_store = AsyncMemoryKeyStoreStub()
        test_oven = AsyncOven(
            root_keystore_for_ops=lambda op: memory_key_store
        )
        ops = [
            bakery.Op("one", "read"),
            bakery.Op("one", "write"),
            bakery.Op("two", "read"),
        ]
        m = await test_oven.macaroon(bakery.VERSION_1, AGES, None, ops)
        got_ops, conds = await test_oven.macaroon_ops([m.macaroon])
        assert len(conds) == 1  # time-before caveat.
        assert bakery.canonical_ops(got_ops) == ops

    async def test_huge_number_of_ops_gives_small_macaroon(self):
        memory_key_store = AsyncMemoryKeyStoreStub()
        test_oven = AsyncOven(
            ops_store=bakery.MemoryOpsStore(),
            root_keystore_for_ops=lambda op: memory_key_store,
        )
        ops = []
        for i in range(30000):
            ops.append(
                bakery.Op(entity="entity" + str(i), action="action" + str(i))
            )

        m = await test_oven.macaroon(bakery.LATEST_VERSION, AGES, None, ops)
        got_ops, conds = await test_oven.macaroon_ops([m.macaroon])
        assert len(conds) == 1  # time-before caveat.
        assert bakery.canonical_ops(got_ops) == bakery.canonical_ops(ops)

        data = m.serialize_json()
        assert len(data) < 300

    async def test_ops_stored_only_once(self):
        st = bakery.MemoryOpsStore()
        memory_key_store = AsyncMemoryKeyStoreStub()
        test_oven = AsyncOven(
            ops_store=st, root_keystore_for_ops=lambda op: memory_key_store
        )
        ops = [
            bakery.Op("one", "read"),
            bakery.Op("one", "write"),
            bakery.Op("two", "read"),
        ]

        m = await test_oven.macaroon(bakery.LATEST_VERSION, AGES, None, ops)
        got_ops, conds = await test_oven.macaroon_ops([m.macaroon])
        assert bakery.canonical_ops(got_ops) == bakery.canonical_ops(ops)

        # Make another macaroon containing the same ops in a different order.
        ops = [
            bakery.Op("one", "write"),
            bakery.Op("one", "read"),
            bakery.Op("one", "read"),
            bakery.Op("two", "read"),
        ]
        await test_oven.macaroon(bakery.LATEST_VERSION, AGES, None, ops)
        assert len(st._store) == 1
