#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from macaroonbakery.bakery import (
    AuthChecker,
    AuthInfo,
    AuthInitError,
    Checker,
    DischargeRequiredError,
    IdentityError,
    LOGIN_OP,
    PermissionDenied,
    VerificationError,
)
from macaroonbakery.bakery._checker import _CaveatSquasher
from pymacaroons import Macaroon


class AsyncChecker(Checker):
    """
    Extend the macaroonbakery.bakery.Checker to return an AsyncAuthChecker when `auth` is called
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def auth(self, mss: list[list[Macaroon]]) -> AuthChecker:
        """
        Returns a new AsyncAuthChecker instance using the given macaroons to
        inform authorization decisions.
        @param mss: a list of macaroon lists.
        """
        return AsyncAuthChecker(parent=self, macaroons=mss)


class AsyncAuthChecker(AuthChecker):
    """
    Extend AuthChecker to allow asynchronous calls to the macaroon opstore
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _init(self, ctx) -> None:
        with self._mutex:
            if not self._executed:
                await self._init_once(ctx)
                self._executed = True

    async def _init_once(self, ctx) -> None:
        self._auth_indexes = {}
        self._conditions = [None] * len(self._macaroons)

        for i, ms in enumerate(self._macaroons):
            try:
                (
                    ops,
                    conditions,
                ) = await self.parent._macaroon_opstore.macaroon_ops(ms)
            except VerificationError as e:
                self._init_errors.append(str(e))
                continue
            except Exception as exc:
                raise AuthInitError(str(exc))  # noqa: B904

            # It's a valid macaroon (in principle - we haven't checked first
            # party caveats).
            self._conditions[i] = conditions
            is_login = False
            for op in ops:
                if op == LOGIN_OP:
                    # Don't associate the macaroon with the login operation
                    # until we've verified that it is valid below
                    is_login = True
                else:
                    if op not in self._auth_indexes:
                        self._auth_indexes[op] = []
                    self._auth_indexes[op].append(i)
            if not is_login:
                continue
            # It's a login macaroon. Check the conditions now -
            # all calls want to see the same authentication
            # information so that callers have a consistent idea of
            # the client's identity.
            #
            # If the conditions fail, we won't use the macaroon for
            # identity, but we can still potentially use it for its
            # other operations if the conditions succeed for those.
            declared, err = self._check_conditions(ctx, LOGIN_OP, conditions)
            if err is not None:
                self._init_errors.append(
                    "cannot authorize login macaroon: " + err
                )
                continue
            if self._identity is not None:
                # We've already found a login macaroon so ignore this one
                # for the purposes of identity.
                continue
            try:
                identity = self.parent._identity_client.declared_identity(
                    ctx, declared
                )
            except IdentityError as exc:
                self._init_errors.append(
                    "cannot decode declared identity: {}".format(exc.args[0])
                )
                continue
            if LOGIN_OP not in self._auth_indexes:
                self._auth_indexes[LOGIN_OP] = []
            self._auth_indexes[LOGIN_OP].append(i)
            self._identity = identity

        if self._identity is None:
            # No identity yet, so try to get one based on the context.
            try:
                identity, cavs = (
                    self.parent._identity_client.identity_from_context(ctx)
                )
            except IdentityError:
                self._init_errors.append("could not determine identity")
            if cavs is None:
                cavs = []
            self._identity, self._identity_caveats = identity, cavs
        return None

    async def allow(self, ctx, ops) -> AuthInfo:
        """Checks that the authorizer's request is authorized to
        perform all the given operations. Note that allow does not check
        first party caveats - if there is more than one macaroon that may
        authorize the request, it will choose the first one that does
        regardless.

        If all the operations are allowed, an AuthInfo is returned holding
        details of the decision and any first party caveats that must be
        checked before actually executing any operation.

        If operations include LOGIN_OP, the request should contain an
        authentication macaroon proving the client's identity. Once an
        authentication macaroon is chosen, it will be used for all other
        authorization requests.

        If an operation was not allowed, an exception will be raised which may
        be:

        - DischargeRequiredError holding the operations that remain to
        be authorized in order to allow authorization to proceed
        - PermissionDenied when no operations can be authorized and there's
        no third party to discharge macaroons for.

        @param ctx AuthContext
        @param ops an array of Op
        :return: an AuthInfo object.
        """
        auth_info, _ = await self.allow_any(ctx, ops)
        return auth_info

    async def allow_any(self, ctx, ops) -> tuple[AuthInfo, list[bool]]:
        """like allow except that it will authorize as many of the
        operations as possible without requiring any to be authorized. If all
        the operations succeeded, the array will be nil.

        If any the operations failed, the returned error will be the same
        that allow would return and each element in the returned slice will
        hold whether its respective operation was allowed.

        If all the operations succeeded, the returned slice will be None.

        The returned AuthInfo will always be non-None.

        The LOGIN_OP operation is treated specially - it is always required if
        present in ops.
        @param ctx AuthContext
        @param ops an array of Op
        :return: an AuthInfo object and the auth used as an array of int.
        """
        authed, used = await self._allow_any(ctx, ops)
        return self._new_auth_info(used), authed

    async def _allow_any(self, ctx, ops) -> tuple[list[bool], list[bool]]:
        await self._init(ctx)
        used = [False] * len(self._macaroons)
        authed = [False] * len(ops)
        num_authed = 0
        errors = []
        for i, op in enumerate(ops):
            for mindex in self._auth_indexes.get(op, []):
                _, err = self._check_conditions(
                    ctx, op, self._conditions[mindex]
                )
                if err is not None:
                    errors.append(err)
                    continue
                authed[i] = True
                num_authed += 1
                used[mindex] = True
                # Use the first authorized macaroon only.
                break
            if op == LOGIN_OP and not authed[i] and self._identity is not None:
                # Allow LOGIN_OP when there's an authenticated user even
                # when there's no macaroon that specifically authorizes it.
                authed[i] = True
        if self._identity is not None:
            # We've authenticated as a user, so even if the operations didn't
            # specifically require it, we add the login macaroon
            # to the macaroons used.
            # Note that the LOGIN_OP conditions have already been checked
            # successfully in initOnceFunc so no need to check again.
            # Note also that there may not be any macaroons if the
            # identity client decided on an identity even with no
            # macaroons.
            for i in self._auth_indexes.get(LOGIN_OP, []):
                used[i] = True
        if num_authed == len(ops):
            # All operations allowed.
            return authed, used
        # There are some unauthorized operations.
        need = []
        need_index = [0] * (len(ops) - num_authed)
        for i, ok in enumerate(authed):
            if not ok:
                need_index[len(need)] = i
                need.append(ops[i])

        # Try to authorize the operations
        # even if we haven't got an authenticated user.
        oks, caveats = self.parent._authorizer.authorize(
            ctx, self._identity, need
        )
        still_need = []
        for i, _ in enumerate(need):
            if i < len(oks) and oks[i]:
                authed[need_index[i]] = True
            else:
                still_need.append(ops[need_index[i]])
        if len(still_need) == 0 and len(caveats) == 0:
            # No more ops need to be authenticated and
            # no caveats to be discharged.
            return authed, used
        if self._identity is None and len(self._identity_caveats) > 0:
            raise DischargeRequiredError(
                msg="authentication required",
                ops=[LOGIN_OP],
                cavs=self._identity_caveats,
            )
        if caveats is None or len(caveats) == 0:
            all_errors = []
            all_errors.extend(self._init_errors)
            all_errors.extend(errors)
            err = ""
            if len(all_errors) > 0:
                err = all_errors[0]
            raise PermissionDenied(err)
        raise DischargeRequiredError(
            msg="some operations have extra caveats", ops=ops, cavs=caveats
        )

    async def allow_capability(self, ctx, ops):
        """Checks that the user is allowed to perform all the
        given operations. If not, a discharge error will be raised.
        If allow_capability succeeds, it returns a list of first party caveat
        conditions that must be applied to any macaroon granting capability
        to execute the operations. Those caveat conditions will not
        include any declarations contained in login macaroons - the
        caller must be careful not to mint a macaroon associated
        with the LOGIN_OP operation unless they add the expected
        declaration caveat too - in general, clients should not create
        capabilities that grant LOGIN_OP rights.

        The operations must include at least one non-LOGIN_OP operation.
        """
        nops = 0
        for op in ops:
            if op != LOGIN_OP:
                nops += 1
        if nops == 0:
            raise ValueError("no non-login operations required in capability")

        _, used = await self._allow_any(ctx, ops)
        squasher = _CaveatSquasher()
        for i, is_used in enumerate(used):
            if not is_used:
                continue
            for cond in self._conditions[i]:
                squasher.add(cond)
        return squasher.final()
