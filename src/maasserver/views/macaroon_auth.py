# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Backend for Macaroon-based authentication."""

__all__ = [
    'MacaroonAuthenticationBackend',
]


from django.contrib.auth.models import User
from maasserver.models import MAASAuthorizationBackend
from macaroonbakery import (
    bakery,
    checkers,
)


class IDClient(bakery.IdentityClient):

    def __init__(self, auth_endpoint):
        self.auth_endpoint = auth_endpoint

    def declared_identity(self, ctx, declared):
        username = declared.get('username')
        if username is None:
            raise bakery.IdentityError('No username found')
        return bakery.SimpleIdentity(user=username)

    def identity_from_context(self, ctx):
        return None, [
            checkers.Caveat(
                condition='is-authenticated-user',
                location=self.auth_endpoint)]


class MacaroonAuthenticationBackend(MAASAuthorizationBackend):
    """An authentication backend getting the user from macaroon identity."""

    def authenticate(self, identity):
        try:
            return User.objects.get(username=identity.id())
        except User.DoesNotExist:
            return None
