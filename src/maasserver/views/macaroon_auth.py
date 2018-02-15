# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Backend for Macaroon-based authentication."""

__all__ = [
    'MacaroonAuthenticationBackend',
]

from datetime import (
    datetime,
    timedelta,
)
import os

from django.contrib.auth import (
    authenticate,
    login,
)
from django.contrib.auth.models import User
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    JsonResponse,
)
from maasserver.models import (
    Config,
    MAASAuthorizationBackend,
    RootKey,
)
from maasserver.utils.views import request_headers
from macaroonbakery import (
    bakery,
    checkers,
    httpbakery,
)


MACAROON_LIFESPAN = timedelta(days=1)


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


class MacaroonDischargeRequest:
    """Return a Macaroon authentication request."""

    def __call__(self, request):
        auth_endpoint = Config.objects.get_config('external_auth_url')
        if not auth_endpoint:
            return HttpResponseNotFound('Not found')

        macaroon_bakery = self._setup_bakery(auth_endpoint, request)
        req_headers = request_headers(request)
        auth_checker = macaroon_bakery.checker.auth(
            httpbakery.extract_macaroons(req_headers))
        try:
            auth_info = auth_checker.allow(
                checkers.AuthContext(), [bakery.LOGIN_OP])
        except bakery.DischargeRequiredError as err:
            return self._authorization_request(
                request, req_headers, macaroon_bakery, err)
        except bakery.PermissionDenied:
            return HttpResponseForbidden()

        user = authenticate(identity=auth_info.identity)
        if user:
            login(request, user)
            data = {'id': user.id, 'username': user.username}
        else:
            data = {'id': None, 'username': auth_info.identity.id()}
        return JsonResponse(data)

    def _setup_bakery(self, auth_endpoint, request):
        return bakery.Bakery(
            key=_get_macaroon_oven_key(),
            root_key_store=KeyStore(MACAROON_LIFESPAN),
            location=request.build_absolute_uri('/'),
            locator=httpbakery.ThirdPartyLocator(
                allow_insecure=not auth_endpoint.startswith('https:')),
            identity_client=IDClient(auth_endpoint),
            authorizer=bakery.ACLAuthorizer(
                get_acl=lambda ctx, op: [bakery.EVERYONE]))

    def _authorization_request(self, request, req_headers, bakery, err):
        """Return a 401 response with a macaroon discharge request."""
        expiry_duration = min(
            MACAROON_LIFESPAN,
            timedelta(seconds=request.session.get_expiry_age()))
        expiration = datetime.utcnow() + expiry_duration
        macaroon = bakery.oven.macaroon(
            httpbakery.request_version(req_headers),
            expiration, err.cavs(), err.ops())
        content, headers = httpbakery.discharge_required_response(
            macaroon, '/', 'authz')
        response = HttpResponse(
            status=401, reason='Unauthorized', content=content)
        for key, value in headers.items():
            response[key] = value
        return response


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
