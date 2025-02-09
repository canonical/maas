# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""OAuth authentication for the various APIs."""

from operator import xor

from piston3.authentication import OAuthAuthentication, send_oauth_error
from piston3.oauth import OAuthError, OAuthMissingParam
from piston3.utils import rc

from maasserver.exceptions import MAASAPIBadRequest, Unauthorized
from maasserver.macaroon_auth import (
    MacaroonAPIAuthentication,
    validate_user_external_auth,
)
from maasserver.models.user import SYSTEM_USERS


class OAuthBadRequest(MAASAPIBadRequest):
    """BadRequest error for OAuth signed requests with invalid parameters."""

    def __init__(self, error):
        super().__init__()
        self.error = error
        self.error.message = f"Bad Request: {error.message}"

    def __str__(self):
        return repr(self.error.message)


class OAuthUnauthorized(Unauthorized):
    """Unauthorized error for OAuth signed requests with invalid tokens."""

    def __init__(self, error):
        super().__init__()
        self.error = error
        # When the error is an authentication error, use a more
        # user-friendly error message.
        if error.message == "Invalid consumer.":
            self.error.message = "Authorization Error: Invalid API key."
        else:
            self.error.message = "Authorization Error: %r" % error.message

    def make_http_response(self):
        return send_oauth_error(self.error)

    def __str__(self):
        return repr(self.error.message)


class MAASAPIAuthentication(OAuthAuthentication):
    """Use the currently logged-in user; resort to OAuth if there isn't one.

    There may be a user already logged-in via another mechanism, like a
    familiar in-browser user/pass challenge.
    """

    def is_authenticated(self, request):
        user = request.user
        if user.is_authenticated:
            # only authenticate if user is local and external auth is disabled
            # or viceversa
            return xor(
                bool(request.external_auth_info), user.userprofile.is_local
            )

        # The following is much the same as is_authenticated from Piston's
        # OAuthAuthentication, with the difference that an OAuth request that
        # does not validate is rejected instead of being silently downgraded.
        if self.is_valid_request(request):
            try:
                consumer, token, parameters = self.validate_token(request)
            except OAuthError as error:
                raise OAuthUnauthorized(error)  # noqa: B904
            except OAuthMissingParam as error:
                raise OAuthBadRequest(error)  # noqa: B904

            if consumer and token:
                user = token.user
                if user.username not in SYSTEM_USERS:
                    external_auth_info = request.external_auth_info
                    is_local_user = user.userprofile.is_local
                    if external_auth_info:
                        if is_local_user:
                            return False
                        if not validate_user_external_auth(
                            user, external_auth_info
                        ):
                            return False
                    elif not is_local_user:
                        return False

                request.user = user
                request.consumer = consumer
                request.throttle_extra = token.consumer.id
                return True

        return False

    def challenge(self, request):
        # Beware: this returns 401: Unauthorized, not 403: Forbidden
        # as the name implies.
        return rc.FORBIDDEN


# OAuth and macaroon-based authentication for the APIs.
api_auth = (
    MAASAPIAuthentication(realm="MAAS API"),
    MacaroonAPIAuthentication(),
)
