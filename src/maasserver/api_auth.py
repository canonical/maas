# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""OAuth authentication for the various APIs."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'api_auth',
    ]

from maasserver.exceptions import Unauthorized
from oauth import oauth
from piston.authentication import (
    OAuthAuthentication,
    send_oauth_error,
    )
from piston.utils import rc


class OAuthUnauthorized(Unauthorized):
    """Unauthorized error for OAuth signed requests with invalid tokens."""

    def __init__(self, error):
        super(OAuthUnauthorized, self).__init__()
        self.error = error

    def make_http_response(self):
        return send_oauth_error(self.error)


class MAASAPIAuthentication(OAuthAuthentication):
    """Use the currently logged-in user; resort to OAuth if there isn't one.

    There may be a user already logged-in via another mechanism, like a
    familiar in-browser user/pass challenge.
    """

    def is_authenticated(self, request):
        if request.user.is_authenticated():
            return request.user

        # The following is much the same as is_authenticated from Piston's
        # OAuthAuthentication, with the difference that an OAuth request that
        # does not validate is rejected instead of being silently downgraded.
        if self.is_valid_request(request):
            try:
                consumer, token, parameters = self.validate_token(request)
            except oauth.OAuthError as error:
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
