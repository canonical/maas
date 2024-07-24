#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from macaroonbakery import bakery, checkers


class _IDClient(bakery.IdentityClient):
    def __init__(self, auth_endpoint, auth_domain=None):
        self.auth_endpoint = auth_endpoint
        self.auth_domain = auth_domain

    def declared_identity(self, ctx, declared):
        username = declared.get("username")
        if username is None:
            raise bakery.IdentityError("No username found")
        return bakery.SimpleIdentity(user=username)

    def identity_from_context(self, ctx):
        return (
            None,
            [
                _get_authentication_caveat(
                    self.auth_endpoint, domain=self.auth_domain
                )
            ],
        )


def _get_macaroon_caveats_ops(auth_endpoint, auth_domain):
    """Return a 2-tuple with lists of caveats and operations for a macaroon."""
    caveats = [_get_authentication_caveat(auth_endpoint, domain=auth_domain)]
    ops = [bakery.LOGIN_OP]
    return caveats, ops


def _get_authentication_caveat(location, domain=""):
    """Return a Caveat requiring the user to be authenticated."""
    condition = "is-authenticated-user"
    if domain:
        condition += " @" + domain
    return checkers.Caveat(condition, location=location)
