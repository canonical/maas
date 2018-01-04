# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""OAuth authentication for the various APIs."""

__all__ = [
    'api_auth',
    ]

from maasserver.exceptions import Unauthorized
from piston3.authentication import (
    OAuthAuthentication,
    send_oauth_error,
)
from piston3.oauth import OAuthError
from piston3.utils import rc


class OAuthUnauthorized(Unauthorized):
    """Unauthorized error for OAuth signed requests with invalid tokens."""

    def __init__(self, error):
        super(OAuthUnauthorized, self).__init__()
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
        if request.user.is_authenticated:
            return request.user

        # The following is much the same as is_authenticated from Piston's
        # OAuthAuthentication, with the difference that an OAuth request that
        # does not validate is rejected instead of being silently downgraded.
        if self.is_valid_request(request):
            try:
                consumer, token, parameters = self.validate_token(request)
            except OAuthError as error:
                raise OAuthUnauthorized(error)

            if consumer and token:
                request.user = token.user
                request.consumer = consumer
                request.throttle_extra = token.consumer.id
                return True

        return False

    def challenge(self):
        # Beware: this returns 401: Unauthorized, not 403: Forbidden
        # as the name implies.
        return rc.FORBIDDEN


# OAuth authentication for the APIs.
api_auth = MAASAPIAuthentication(realm="MAAS API")
