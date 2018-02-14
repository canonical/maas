# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Backend for Macaroon-based authentication."""

__all__ = [
    'MacaroonAuthenticationBackend',
]

from datetime import datetime
import os

from django.contrib.auth.models import User
from maasserver.models import (
    Config,
    MAASAuthorizationBackend,
    RootKey,
)
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


class KeyStore:
    """A database-backed RootKeyStore for root keys.

    :param expiry_duration: the minimum length of time that root keys will be
        valid for after they are returned. The maximum length of time that they
        will be valid for expiry_duration + generate_interval.
    :type expiry_duration: datetime.timedelta

    :param generate_interval: the maximum length of time for which a root key
        will be returned. If None, it defaults to expiry_duration.
    :type generate_interval: datetime.timedelta

    """

    # size in bytes of the key
    KEY_LENGTH = 24

    def __init__(self, expiry_duration, generate_interval=None,
                 now=datetime.utcnow):
        self.expiry_duration = expiry_duration
        self.generate_interval = generate_interval
        if generate_interval is None:
            self.generate_interval = expiry_duration
        self._now = now

    def get(self, id):
        """Return the key with the specified bytes string id."""
        try:
            key = RootKey.objects.get(pk=int(id))
        except (ValueError, RootKey.DoesNotExist):
            return None

        if key.expiration < self._now():
            key.delete()
            return None
        return bytes(key.material)

    def root_key(self):
        """Return the root key and its id as a byte string."""
        key = self._find_best_key()
        if not key:
            # delete expired keys (if any)
            RootKey.objects.filter(expiration__lt=self._now()).delete()
            key = self._new_key()

        return bytes(key.material), str(key.id).encode('ascii')

    def _find_best_key(self):
        now = self._now()
        qs = RootKey.objects.filter(
            created__gte=now - self.generate_interval,
            expiration__gte=now - self.expiry_duration,
            expiration__lte=(
                now + self.expiry_duration + self.generate_interval))
        qs = qs.order_by('-created')
        return qs.first()

    def _new_key(self):
        now = self._now()
        expiration = now + self.expiry_duration + self.generate_interval
        key = RootKey(
            material=os.urandom(self.KEY_LENGTH), created=now,
            expiration=expiration)
        key.save()
        return key


def _get_macaroon_oven_key():
    """Return a private key to use for macaroon caveats signing.

    The key is read from the Config if found, otherwise a new one is created
    and saved.

    """
    material = Config.objects.get_config('macaroon_private_key')
    if material:
        return bakery.PrivateKey.deserialize(material)

    key = bakery.generate_key()
    Config.objects.set_config(
        'macaroon_private_key', key.serialize().decode('ascii'))
    return key
