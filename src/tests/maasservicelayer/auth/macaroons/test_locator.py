#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from macaroonbakery import bakery
import pytest

from maasservicelayer.auth.macaroons.locator import AsyncThirdPartyLocator


@pytest.mark.asyncio
class TestKeyRing:
    """
    Async porting of https://git.launchpad.net/ubuntu/+source/py-macaroon-bakery/tree/macaroonbakery/tests/test_keyring.py
    """

    async def test_cache_fetch(self, mock_aioresponse) -> None:
        key = bakery.generate_key()

        mock_aioresponse.get(
            url="http://test/discharge/info",
            status=200,
            payload={
                "Version": bakery.LATEST_VERSION,
                "PublicKey": str(key.public_key),
            },
        )

        expectInfo = bakery.ThirdPartyInfo(
            public_key=key.public_key, version=bakery.LATEST_VERSION
        )
        kr = AsyncThirdPartyLocator(allow_insecure=True)
        info = await kr.third_party_info("http://test/")
        await kr.close()

        assert info == expectInfo

    async def test_cache_norefetch(self, mock_aioresponse):
        key = bakery.generate_key()

        mock_aioresponse.get(
            url="http://test/discharge/info",
            status=200,
            payload={
                "Version": bakery.LATEST_VERSION,
                "PublicKey": str(key.public_key),
            },
        )

        expectInfo = bakery.ThirdPartyInfo(
            public_key=key.public_key, version=bakery.LATEST_VERSION
        )
        kr = AsyncThirdPartyLocator(allow_insecure=True)
        info = await kr.third_party_info("http://test/")
        assert info == expectInfo
        info = await kr.third_party_info("http://test/")
        await kr.close()
        assert info == expectInfo

    async def test_cache_fetch_no_version(self, mock_aioresponse):
        key = bakery.generate_key()

        mock_aioresponse.get(
            url="http://test/discharge/info",
            status=200,
            payload={
                "PublicKey": str(key.public_key),
            },
        )

        expectInfo = bakery.ThirdPartyInfo(
            public_key=key.public_key, version=bakery.VERSION_1
        )
        kr = AsyncThirdPartyLocator(allow_insecure=True)
        info = await kr.third_party_info("http://test/")
        await kr.close()
        assert info == expectInfo

    async def test_allow_insecure(self):
        kr = AsyncThirdPartyLocator()
        with pytest.raises(bakery.ThirdPartyInfoNotFound):
            await kr.third_party_info("http://test/")
        await kr.close()

    async def test_fallback(self, mock_aioresponse):
        key = bakery.generate_key()

        mock_aioresponse.get(url="http://test/discharge/info", status=404)

        mock_aioresponse.get(
            url="http://test/publickey",
            status=200,
            payload={
                "PublicKey": str(key.public_key),
            },
        )

        expectInfo = bakery.ThirdPartyInfo(
            public_key=key.public_key, version=bakery.VERSION_1
        )
        kr = AsyncThirdPartyLocator(allow_insecure=True)
        info = await kr.third_party_info("http://test/")
        await kr.close()
        assert info == expectInfo
