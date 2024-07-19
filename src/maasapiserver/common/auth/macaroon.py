#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import os

from macaroonbakery import checkers
from macaroonbakery.bakery import encode_caveat, ThirdPartyInfo, VERSION_3
from macaroonbakery.bakery._macaroon import _parse_local_location, Macaroon


class AsyncMacaroon(Macaroon):
    """
    Async porting of macaroonbakery.bakery._macaroon.Macaroon.
    We have to override the add_caveat because third_party_info is retrieved from an external service and
    we need to use an async http client.
    """

    async def add_caveat(self, cav, key=None, loc=None):
        """Add a caveat to the macaroon.

        It encrypts it using the given key pair
        and by looking up the location using the given locator.
        As a special case, if the caveat's Location field has the prefix
        "local " the caveat is added as a client self-discharge caveat using
        the public key base64-encoded in the rest of the location. In this
        case, the Condition field must be empty. The resulting third-party
        caveat will encode the condition "true" encrypted with that public
        key.

        @param cav the checkers.Caveat to be added.
        @param key the public key to encrypt third party caveat.
        @param loc locator to find information on third parties when adding
        third party caveats. It is expected to have a third_party_info method
        that will be called with a location string and should return a
        ThirdPartyInfo instance holding the requested information.
        """
        if cav.location is None:
            self._macaroon.add_first_party_caveat(
                self.namespace.resolve_caveat(cav).condition
            )
            return
        if key is None:
            raise ValueError("no private key to encrypt third party caveat")
        local_info = _parse_local_location(cav.location)
        if local_info is not None:
            if cav.condition:
                raise ValueError(
                    "cannot specify caveat condition in "
                    "local third-party caveat"
                )
            info = local_info
            cav = checkers.Caveat(location="local", condition="true")
        else:
            if loc is None:
                raise ValueError("no locator when adding third party caveat")
            info = await loc.third_party_info(cav.location)

        root_key = os.urandom(24)

        # Use the least supported version to encode the caveat.
        if self._version < info.version:
            info = ThirdPartyInfo(
                version=self._version,
                public_key=info.public_key,
            )

        caveat_info = encode_caveat(
            cav.condition, root_key, info, key, self._namespace
        )
        if info.version < VERSION_3:
            # We're encoding for an earlier client or third party which does
            # not understand bundled caveat info, so use the encoded
            # caveat information as the caveat id.
            id = caveat_info
        else:
            id = self._new_caveat_id(self._caveat_id_prefix)
            self._caveat_data[id] = caveat_info

        self._macaroon.add_third_party_caveat(cav.location, root_key, id)

    async def add_caveats(self, cavs, key, loc):
        """Add an array of caveats to the macaroon.

        This method does not mutate the current object.
        @param cavs arrary of caveats.
        @param key the PublicKey to encrypt third party caveat.
        @param loc locator to find the location object that has a method
        third_party_info.
        """
        if cavs is None:
            return
        for cav in cavs:
            await self.add_caveat(cav, key, loc)
