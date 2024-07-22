#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timedelta

from macaroonbakery import bakery, checkers, httpbakery
from macaroonbakery.bakery import DischargeRequiredError
from macaroonbakery.bakery._store import RootKeyStore
import pytest

from maasapiserver.common.auth.checker import AsyncChecker
from maasapiserver.common.auth.locator import AsyncThirdPartyLocator
from maasapiserver.common.auth.oven import AsyncOven
from maasserver.auth.macaroons import _IDClient
from provisioningserver.security import to_bin


class _StoppedClock(object):
    def __init__(self, t):
        self.t = t

    def utcnow(self):
        return self.t


def get_test_context(epoch: datetime):
    return checkers.context_with_clock(
        checkers.AuthContext(), _StoppedClock(epoch)
    )


class _DischargerLocator(AsyncThirdPartyLocator):
    def __init__(self, dischargers=None):
        if dischargers is None:
            dischargers = {}
        self._dischargers = dischargers

    async def third_party_info(self, loc):
        d = self._dischargers.get(loc)
        if d is None:
            return None
        return bakery.ThirdPartyInfo(
            public_key=d._key.public_key,
            version=bakery.LATEST_VERSION,
        )

    def __setitem__(self, key, item):
        self._dischargers[key] = item

    def __getitem__(self, key):
        return self._dischargers[key]

    def get(self, key):
        return self._dischargers.get(key)


class _OpStore(RootKeyStore):

    def __init__(self, key):
        self.key = to_bin(key)

    async def get(self, id):
        return self.key

    async def root_key(self):
        return self.key


VALID_ISSUED_TIME = datetime(
    year=2024, month=7, day=22, hour=6, minute=36, second=13
)
VALID_MACAROON_KEY = "SOgnhQ+dcZuCGm03boCauHK4KB3PiK8xi808mq49lpw="
VALID_ROOTKEY = "4ccd727c3615251746ffeeeeb204b8b6a779ff26bbd97447"
VALID_MACAROON_HEADER = {
    "Cookie": "macaroon-maas=W3siaWRlbnRpZmllciI6ICJBd29RUWh2MUVQM1YtTHR2Z"
    "kg2RmJ5MF80UklCT1JvT0NnVnNiMmRwYmhJRmJHOW5hVzQiLCAic2lnbmF0"
    "dXJlIjogIjk0NDUzMmVjODYxZGJiNDFiNjBlNDdlOWE1Y2IzODFiMDc5MjU"
    "3MDJhYTVkNGI0MTYzYTJkZDEzZWRmMTYzZjEiLCAibG9jYXRpb24iOiAiaH"
    "R0cDovL2xvY2FsaG9zdDo1MjQwLyIsICJjYXZlYXRzIjogW3siY2lkIjogI"
    "nRpbWUtYmVmb3JlIDIwMjQtMDctMjJUMDY6Mzc6NTQuMjA1MTc3WiJ9LCB7"
    "ImNpZCI6ICJleUpVYUdseVpGQmhjblI1VUhWaWJHbGpTMlY1SWpvZ0luTXh"
    "kMVZhVFdGMlUydFNUalZwYzJKYVdYUmhNRll5Y3pFd1JtMHhlSEkxZW1oc1"
    "ZFVklWVVF6UVhjOUlpd2dJa1pwY25OMFVHRnlkSGxRZFdKc2FXTkxaWGtpT"
    "2lBaWRXczJlbnBPYmt4SFUxRjJlRVZzYml0NmRsUnJlVkZtYWtOU1pIZFpX"
    "SEZaYkdwd2FuZFRXUzluUlQwaUxDQWlUbTl1WTJVaU9pQWlWME5EV1hKb1p"
    "sVTVaVU5JZGsxaVZETm1jWFJaY25Odk4wWkdZMlp5ZEhRaUxDQWlTV1FpT2"
    "lBaWN6VmlValExWlV3ME4wNVBhazloVTBOQlp6aEtZa013ZHpVcldrMTNVW"
    "FpUTUcxUlJEWlhkRXgzVVV4M1ZGUlZTV1ZTTlU1VWJWRXJlblo0V1dKeVRs"
    "cGFNMmhGY1cxa09IWnFRbWczTUdSbVkwNUpiMFI1YTBaQ2FERk1Nall4YTF"
    "KcWJETm1XRmhNWWtwbVdYaG9MeXRZTmtsNk9GTm1aa2sxWlRsQ1dtSXZOWF"
    "ZLVERNMFBTSjkiLCAidmlkIjogIm1CdjlHOGFhRllEb1VsQVhIS0NIS014d"
    "Whsdmo0c3o0Qld2cUJCb1NtUlRvXzhuNlNwN3BkdlAtZU9iUnVraWllX1ZZ"
    "R2dRZzB4OXRfWm9fMndVVW14R0FaMENyaHJJSCIsICJjbCI6ICJodHRwOi8"
    "vMTAuMC4xLjIzOjUwMDAvYXV0aCJ9XX0seyJpZGVudGlmaWVyIjogImV5Sl"
    "VhR2x5WkZCaGNuUjVVSFZpYkdsalMyVjVJam9nSW5NeGQxVmFUV0YyVTJ0U"
    "1RqVnBjMkphV1hSaE1GWXljekV3Um0weGVISTFlbWhzVkVWSVZVUXpRWGM5"
    "SWl3Z0lrWnBjbk4wVUdGeWRIbFFkV0pzYVdOTFpYa2lPaUFpZFdzMmVucE9"
    "ia3hIVTFGMmVFVnNiaXQ2ZGxScmVWRm1ha05TWkhkWldIRlpiR3B3YW5kVF"
    "dTOW5SVDBpTENBaVRtOXVZMlVpT2lBaVYwTkRXWEpvWmxVNVpVTklkazFpV"
    "kRObWNYUlpjbk52TjBaR1kyWnlkSFFpTENBaVNXUWlPaUFpY3pWaVVqUTFa"
    "VXcwTjA1UGFrOWhVME5CWnpoS1lrTXdkelVyV2sxM1VYWlRNRzFSUkRaWGR"
    "FeDNVVXgzVkZSVlNXVlNOVTVVYlZFcmVuWjRXV0p5VGxwYU0yaEZjVzFrT0"
    "hacVFtZzNNR1JtWTA1SmIwUjVhMFpDYURGTU1qWXhhMUpxYkRObVdGaE1Za"
    "3BtV1hob0x5dFlOa2w2T0ZObVprazFaVGxDV21Jdk5YVktURE0wUFNKOSIs"
    "ICJzaWduYXR1cmUiOiAiNDE2ZDYyN2VjNWI0ZTk3Nzc1MTY0ZTQ3ZGVkY2I"
    "2ODc0MDkyZmJiOGRlMjU0MzgzNzc1OGQxMWI3YTg3YjliNCIsICJjYXZlYX"
    "RzIjogW3siY2lkIjogImRlY2xhcmVkIHVzZXJuYW1lIGFkbWluIn1dfV0="
}

INVALID_MACAROON_HEADER = {
    "Cookie": "macaroon-maas=W3siaWRlbnRpZmllciI6ICJBd29RX003cFlXRnJTOHhseF"
    "YzSVVFcmdYeElCTnhvT0NnVnNiMmRwYmhJRmJHOW5hVzQiLCAic2lnbmF0dX"
    "JlIjogImUxODQ5ZDgyNjdhMmE5ODg0ZTg3NGMzNDAwZTEwNTI2NjZmOGIxNj"
    "NlYjA0Mjk0YWY1MTJjMzEyODg5YjE3NWEiLCAibG9jYXRpb24iOiAiaHR0cD"
    "ovL2xvY2FsaG9zdDo1MjQwLyIsICJjYXZlYXRzIjogW3siY2lkIjogInRpbW"
    "UtYmVmb3JlIDIwMjQtMDctMTlUMTU6MTc6MDUuNjY1NzcxWiJ9LCB7ImNpZC"
    "I6ICJleUpVYUdseVpGQmhjblI1VUhWaWJHbGpTMlY1SWpvZ0luTXhkMVZhVF"
    "dGMlUydFNUalZwYzJKYVdYUmhNRll5Y3pFd1JtMHhlSEkxZW1oc1ZFVklWVV"
    "F6UVhjOUlpd2dJa1pwY25OMFVHRnlkSGxRZFdKc2FXTkxaWGtpT2lBaWRXcz"
    "JlbnBPYmt4SFUxRjJlRVZzYml0NmRsUnJlVkZtYWtOU1pIZFpXSEZaYkdwd2"
    "FuZFRXUzluUlQwaUxDQWlUbTl1WTJVaU9pQWlNMmhEU1hGTmF5dFVlV3hDY0"
    "VwS2JFcG9kVFpIVmpkNk5GZDJPWFJsYmtRaUxDQWlTV1FpT2lBaWIxSlJPRT"
    "FpYnpkQllXbG9aVFJPUW5OV2REUnVWMVEzU1RScGFVVTFRMXB1V1hWQ2RTdF"
    "ZSbVJEZUhOTFQxVk1jaXRoVlc1SlUwaDVVR3B1WjFKc1RGazNNRlZTWlhSNE"
    "9HbGthVlpMUjNWeGRYSnNUMlUyY1VVMGFFaDRZbE5MWjNWaGIwMW1lamxFVG"
    "s5cWVUQkVRMDVwT1dkR2JFMU5jSGhuU0doelpXZEhRMHBzTWt4alBTSjkiLC"
    "AidmlkIjogInJHamZ2QUYzMk1LZjQ2OVZidnZEb2hfSE1YOFVTVmRzZTVRVj"
    "VwYTFFUEJpSnZTcUdnZTJHTzkyVzQyWUhENnB0TzIwR1ZGeWFqNENZTUZ5Qm"
    "RHZ3EyaTU2TXdHVVpjbSIsICJjbCI6ICJodHRwOi8vMTAuMC4xLjIzOjUwMD"
    "AvYXV0aCJ9XX0seyJpZGVudGlmaWVyIjogImV5SlVhR2x5WkZCaGNuUjVVSF"
    "ZpYkdsalMyVjVJam9nSW5NeGQxVmFUV0YyVTJ0U1RqVnBjMkphV1hSaE1GWX"
    "ljekV3Um0weGVISTFlbWhzVkVWSVZVUXpRWGM5SWl3Z0lrWnBjbk4wVUdGeW"
    "RIbFFkV0pzYVdOTFpYa2lPaUFpZFdzMmVucE9ia3hIVTFGMmVFVnNiaXQ2ZG"
    "xScmVWRm1ha05TWkhkWldIRlpiR3B3YW5kVFdTOW5SVDBpTENBaVRtOXVZMl"
    "VpT2lBaU0yaERTWEZOYXl0VWVXeENjRXBLYkVwb2RUWkhWamQ2TkZkMk9YUm"
    "xia1FpTENBaVNXUWlPaUFpYjFKUk9FMWliemRCWVdsb1pUUk9Rbk5XZERSdV"
    "YxUTNTVFJwYVVVMVExcHVXWFZDZFN0VlJtUkRlSE5MVDFWTWNpdGhWVzVKVT"
    "BoNVVHcHVaMUpzVEZrM01GVlNaWFI0T0dsa2FWWkxSM1Z4ZFhKc1QyVTJjVV"
    "UwYUVoNFlsTkxaM1ZoYjAxbWVqbEVUazlxZVRCRVEwNXBPV2RHYkUxTmNIaG"
    "5TR2h6WldkSFEwcHNNa3hqUFNKOSIsICJzaWduYXR1cmUiOiAiNjhmNTM4ZD"
    "ExZjRlMzQ5ZjYwMTQzZGJjYmYzOTI2MjcxZjJjZDVjNGEzY2MxZDEzZDJmYj"
    "JiNTAxOWQ4NWYyZCIsICJjYXZlYXRzIjogW3siY2lkIjogImRlY2xhcmVkIH"
    "VzZXJuYW1lIGFkbWluIn1dfV0="
}


class TestAsyncAuthChecker:
    @pytest.mark.asyncio
    async def test_valid_macaroon1(self):
        locator = _DischargerLocator()
        checker = checkers.Checker()
        test_context = get_test_context(VALID_ISSUED_TIME)
        storage = _OpStore(key=VALID_ROOTKEY)
        oven = AsyncOven(
            key=VALID_MACAROON_KEY,
            location="http://localhost:5240/",
            locator=locator,
            namespace=checker.namespace(),
            root_keystore_for_ops=lambda op: storage,
            ops_store=None,
        )
        checker = AsyncChecker(
            checker=checker,
            authorizer=bakery.ACLAuthorizer(
                get_acl=lambda ctx, op: [bakery.EVERYONE]
            ),
            identity_client=_IDClient(
                "http://10.0.1.23:5000/", auth_domain=""
            ),
            macaroon_opstore=oven,
        )

        auth = checker.auth(
            mss=httpbakery.extract_macaroons(VALID_MACAROON_HEADER)
        )
        auth_info = await auth.allow(test_context, [bakery.LOGIN_OP])
        assert auth_info.identity.id() == "admin"

        auth = checker.auth(
            mss=httpbakery.extract_macaroons(INVALID_MACAROON_HEADER)
        )
        with pytest.raises(DischargeRequiredError):
            await auth.allow(test_context, [bakery.LOGIN_OP])

    @pytest.mark.asyncio
    async def test_expired_macaroon(self):
        locator = _DischargerLocator()
        checker = checkers.Checker()
        # Expired
        test_context = get_test_context(VALID_ISSUED_TIME + timedelta(days=1))
        storage = _OpStore(key=VALID_ROOTKEY)
        oven = AsyncOven(
            key=VALID_MACAROON_KEY,
            location="http://localhost:5240/",
            locator=locator,
            namespace=checker.namespace(),
            root_keystore_for_ops=lambda op: storage,
            ops_store=None,
        )
        checker = AsyncChecker(
            checker=checker,
            authorizer=bakery.ACLAuthorizer(
                get_acl=lambda ctx, op: [bakery.EVERYONE]
            ),
            identity_client=_IDClient(
                "http://10.0.1.23:5000/", auth_domain=""
            ),
            macaroon_opstore=oven,
        )

        auth = checker.auth(
            mss=httpbakery.extract_macaroons(VALID_MACAROON_HEADER)
        )
        with pytest.raises(DischargeRequiredError):
            await auth.allow(test_context, [bakery.LOGIN_OP])
