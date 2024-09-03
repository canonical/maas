#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from macaroonbakery import checkers
from macaroonbakery._utils import raw_urlsafe_b64encode
from macaroonbakery.bakery import (
    canonical_ops,
    LATEST_VERSION,
    Macaroon,
    macaroon_version,
    Op,
    Oven,
    VerificationError,
)
from macaroonbakery.bakery._oven import _decode_macaroon_id
from pymacaroons import MACAROON_V2, Verifier

from maasservicelayer.auth.macaroons.macaroon import AsyncMacaroon


class AsyncOven(Oven):
    """
    Async porting of macaroonbakery.bakery.Oven.
    This is needed because the root keys are stored in the DB and we need to await the call.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def macaroon(self, version, expiry, caveats, ops) -> Macaroon:
        """Takes a macaroon with the given version from the oven,
        associates it with the given operations and attaches the given caveats.
        There must be at least one operation specified.
        The macaroon will expire at the given time - a time_before first party
        caveat will be added with that time.

        @return: a new Macaroon object.
        """
        if len(ops) == 0:
            raise ValueError(
                "cannot mint a macaroon associated " "with no operations"
            )

        ops = canonical_ops(ops)
        root_key, storage_id = await self.root_keystore_for_ops(ops).root_key()

        id = self._new_macaroon_id(storage_id, expiry, ops)

        id_bytes = bytes((LATEST_VERSION,)) + id.SerializeToString()

        if macaroon_version(version) < MACAROON_V2:
            # The old macaroon format required valid text for the macaroon id,
            # so base64-encode it.
            id_bytes = raw_urlsafe_b64encode(id_bytes)

        m = AsyncMacaroon(
            root_key,
            id_bytes,
            self.location,
            version,
            self.namespace,
        )
        await m.add_caveat(
            checkers.time_before_caveat(expiry), self.key, self.locator
        )
        await m.add_caveats(caveats, self.key, self.locator)
        return m

    async def macaroon_ops(self, macaroons) -> tuple[list[Op], list[str]]:
        """This method makes the oven satisfy the MacaroonOpStore protocol
        required by the Checker class.

        For macaroons minted with previous bakery versions, it always
        returns a single LoginOp operation.

        :param macaroons:
        :return:
        """
        if len(macaroons) == 0:
            raise ValueError("no macaroons provided")

        storage_id, ops = _decode_macaroon_id(macaroons[0].identifier_bytes)
        root_key = await self.root_keystore_for_ops(ops).get(storage_id)
        if root_key is None:
            raise VerificationError("macaroon key not found in storage")
        v = Verifier()
        conditions = []

        def validator(condition):
            # Verify the macaroon's signature only. Don't check any of the
            # caveats yet but save them so that we can return them.
            conditions.append(condition)
            return True

        v.satisfy_general(validator)
        try:
            v.verify(macaroons[0], root_key, macaroons[1:])
        except Exception as exc:
            # Unfortunately pymacaroons doesn't control
            # the set of exceptions that can be raised here.
            # Possible candidates are:
            # pymacaroons.exceptions.MacaroonUnmetCaveatException
            # pymacaroons.exceptions.MacaroonInvalidSignatureException
            # ValueError
            # nacl.exceptions.CryptoError
            #
            # There may be others too, so just catch everything.
            raise VerificationError(
                "verification failed: {}".format(str(exc))
            ) from exc

        if (
            self.ops_store is not None
            and len(ops) == 1
            and ops[0].entity.startswith("multi-")
        ):
            # It's a multi-op entity, so retrieve the actual operations
            # it's associated with.
            ops = self.ops_store.get_ops(ops[0].entity)

        return ops, conditions
