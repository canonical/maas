# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""OAuth authentication for the various APIs."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'api_auth',
    ]

from piston.authentication import OAuthAuthentication
from piston.utils import rc


class MaasAPIAuthentication(OAuthAuthentication):
    """A piston authentication class that uses the currently logged-in user
    if there is one, and defaults to piston's OAuthAuthentication if not.

    """

    def is_authenticated(self, request):
        if request.user.is_authenticated():
            return request.user
        else:
            return super(
                MaasAPIAuthentication, self).is_authenticated(request)

    def challenge(self):
        # Beware: this returns 401: Unauthorized, not 403: Forbidden
        # as the name implies.
        return rc.FORBIDDEN


# OAuth authentication for the APIs.
api_auth = MaasAPIAuthentication(realm="MaaS API")
