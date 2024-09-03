#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import json

import macaroonbakery.bakery as bakery
from macaroonbakery.bakery import ThirdPartyStore
import macaroonbakery.checkers as checkers
from macaroonbakery.tests import common
import pytest

from maasservicelayer.auth.macaroons.macaroon import AsyncMacaroon


class AsyncThirdPartyStoreStub(ThirdPartyStore):
    async def third_party_info(self, loc):
        return super().third_party_info(loc)


@pytest.mark.asyncio
class TestAsyncMacaroon:
    """
    Tests taken from https://git.launchpad.net/ubuntu/+source/py-macaroon-bakery/tree/macaroonbakery/tests/test_macaroon.py
    and adapted to the new async override
    """

    async def test_add_first_party_caveat(self):
        m = AsyncMacaroon("rootkey", "some id", "here", bakery.LATEST_VERSION)
        await m.add_caveat(checkers.Caveat("test_condition"))
        caveats = m.first_party_caveats()
        assert len(caveats) == 1
        assert caveats[0].caveat_id == b"test_condition"

    async def test_add_third_party_caveat(self):
        locator = AsyncThirdPartyStoreStub()
        bs = common.new_bakery("bs-loc", locator)

        lbv = bytes((bakery.LATEST_VERSION,))
        tests = [
            ("no existing id", b"", [], lbv + bytes((0,))),
            (
                "several existing ids",
                b"",
                [
                    lbv + bytes((0,)),
                    lbv + bytes((1,)),
                    lbv + bytes((2,)),
                ],
                lbv + bytes((3,)),
            ),
            (
                "with base id",
                lbv + bytes((0,)),
                [lbv + bytes((0,))],
                lbv + bytes((0,)) + bytes((0,)),
            ),
            (
                "with base id and existing id",
                lbv + bytes((0,)),
                [lbv + bytes((0,)) + bytes((0,))],
                lbv + bytes((0,)) + bytes((1,)),
            ),
        ]

        for test in tests:
            print("test ", test[0])
            m = AsyncMacaroon(
                root_key=b"root key",
                id=b"id",
                location="location",
                version=bakery.LATEST_VERSION,
            )
            for id in test[2]:
                m.macaroon.add_third_party_caveat(
                    key=None, key_id=id, location=""
                )
                m._caveat_id_prefix = test[1]
            await m.add_caveat(
                checkers.Caveat(location="bs-loc", condition="something"),
                bs.oven.key,
                locator,
            )
            assert m.macaroon.caveats[len(test[2])].caveat_id == test[3]

    async def test_marshal_json_latest_version(self):
        locator = AsyncThirdPartyStoreStub()
        bs = common.new_bakery("bs-loc", locator)
        ns = checkers.Namespace(
            {
                "testns": "x",
                "otherns": "y",
            }
        )
        m = AsyncMacaroon(
            root_key=b"root key",
            id=b"id",
            location="location",
            version=bakery.LATEST_VERSION,
            namespace=ns,
        )
        await m.add_caveat(
            checkers.Caveat(location="bs-loc", condition="something"),
            bs.oven.key,
            locator,
        )
        data = m.serialize_json()
        m1 = bakery.Macaroon.deserialize_json(data)
        # Just check the signature and version - we're not interested in fully
        # checking the macaroon marshaling here.
        assert m1.macaroon.signature == m.macaroon.signature
        assert m1.macaroon.version == m.macaroon.version
        assert len(m1.macaroon.caveats) == 1
        assert m1.namespace == m.namespace
        assert m1._caveat_data == m._caveat_data

        # test with the encoder, decoder
        data = json.dumps(m, cls=bakery.MacaroonJSONEncoder)
        m1 = json.loads(data, cls=bakery.MacaroonJSONDecoder)
        assert m1.macaroon.signature == m.macaroon.signature
        assert m1.macaroon.version == m.macaroon.version
        assert len(m1.macaroon.caveats) == 1
        assert m1.namespace == m.namespace
        assert m1._caveat_data == m._caveat_data

    async def _test_json_with_version(self, version):
        locator = AsyncThirdPartyStoreStub()
        bs = common.new_bakery("bs-loc", locator)

        ns = checkers.Namespace(
            {
                "testns": "x",
            }
        )

        m = AsyncMacaroon(
            root_key=b"root key",
            id=b"id",
            location="location",
            version=version,
            namespace=ns,
        )
        await m.add_caveat(
            checkers.Caveat(location="bs-loc", condition="something"),
            bs.oven.key,
            locator,
        )

        # Sanity check that no external caveat data has been added.
        assert len(m._caveat_data) == 0

        data = json.dumps(m, cls=bakery.MacaroonJSONEncoder)
        m1 = json.loads(data, cls=bakery.MacaroonJSONDecoder)

        # Just check the signature and version - we're not interested in fully
        # checking the macaroon marshaling here.
        assert m1.macaroon.signature == m.macaroon.signature
        assert m1.macaroon.version == bakery.macaroon_version(version)
        assert len(m1.macaroon.caveats) == 1

        # Namespace information has been thrown away.
        assert m1.namespace == bakery.legacy_namespace()

        assert len(m1._caveat_data) == 0

    async def test_clone(self):
        locator = AsyncThirdPartyStoreStub()
        bs = common.new_bakery("bs-loc", locator)
        ns = checkers.Namespace(
            {
                "testns": "x",
            }
        )
        m = AsyncMacaroon(
            root_key=b"root key",
            id=b"id",
            location="location",
            version=bakery.LATEST_VERSION,
            namespace=ns,
        )
        await m.add_caveat(
            checkers.Caveat(location="bs-loc", condition="something"),
            bs.oven.key,
            locator,
        )
        m1 = m.copy()
        assert len(m.macaroon.caveats) == 1
        assert len(m1.macaroon.caveats) == 1
        assert m._caveat_data, m1._caveat_data
        await m.add_caveat(
            checkers.Caveat(location="bs-loc", condition="something"),
            bs.oven.key,
            locator,
        )
        assert len(m.macaroon.caveats) == 2
        assert len(m1.macaroon.caveats) == 1
        assert m._caveat_data != m1._caveat_data

    async def test_json_deserialize_from_go(self):
        ns = checkers.Namespace()
        ns.register("someuri", "x")
        m = AsyncMacaroon(
            root_key=b"rootkey",
            id=b"some id",
            location="here",
            version=bakery.LATEST_VERSION,
            namespace=ns,
        )
        await m.add_caveat(
            checkers.Caveat(condition="something", namespace="someuri")
        )
        data = (
            '{"m":{"c":[{"i":"x:something"}],"l":"here","i":"some id",'
            '"s64":"c8edRIupArSrY-WZfa62pgZFD8VjDgqho9U2PlADe-E"},"v":3,'
            '"ns":"someuri:x"}'
        )
        m_go = bakery.Macaroon.deserialize_json(data)

        assert m.macaroon.signature_bytes == m_go.macaroon.signature_bytes
        assert m.macaroon.version == m_go.macaroon.version
        assert len(m_go.macaroon.caveats) == 1
        assert m.namespace == m_go.namespace
