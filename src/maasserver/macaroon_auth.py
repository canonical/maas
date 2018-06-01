# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Backend for Macaroon-based authentication."""

__all__ = [
    'MacaroonAPIAuthentication',
    'MacaroonAuthorizationBackend',
    'MacaroonDischargeRequest',
    'validate_user_external_auth',
]

from datetime import (
    datetime,
    timedelta,
)
import os
from urllib.parse import quote

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
from maasserver.models.user import SYSTEM_USERS
from maasserver.utils.views import request_headers
from macaroonbakery import (
    bakery,
    checkers,
    httpbakery,
)
from macaroonbakery.httpbakery.agent import (
    Agent,
    AgentInteractor,
    AuthInfo,
)
from piston3.utils import rc
import requests


MACAROON_LIFESPAN = timedelta(days=1)

IDM_USER_CHECK_INTERVAL = timedelta(hours=1)


class MacaroonAuthorizationBackend(MAASAuthorizationBackend):
    """An authorization backend getting the user from macaroon identity."""

    def authenticate(self, request, identity=None):
        if not request.external_auth_info or not identity:
            return

        username = identity.id()
        try:
            user = User.objects.get(username=username)
            if username not in SYSTEM_USERS and user.userprofile.is_local:
                return
        except User.DoesNotExist:
            user = User(username=username, is_superuser=True)
            user.save()

        if not user.is_active:
            # the user was previously marked as inactive, but is now
            # authenticated from external source, so it should be reactivated
            user.is_active = True
            user.save()
        return user


class MacaroonAPIAuthentication:
    """A Piston authentication backend using macaroons."""

    def is_authenticated(self, request):
        if not request.external_auth_info:
            return False

        req_headers = request_headers(request)
        macaroon_bakery = _get_bakery(request)
        auth_checker = macaroon_bakery.checker.auth(
            httpbakery.extract_macaroons(req_headers))
        try:
            auth_info = auth_checker.allow(
                checkers.AuthContext(), [bakery.LOGIN_OP])
        except (bakery.DischargeRequiredError, bakery.PermissionDenied):
            return False

        # set the user in the request so that it's considered authenticated. If
        # a user is not found with the username from the identity, it's
        # created.
        username = auth_info.identity.id()
        try:
            user = User.objects.get(username=username)
            if user.userprofile.is_local:
                return False
            created = False
        except User.DoesNotExist:
            user = User(username=username, is_superuser=True)
            user.save()
            created = True

        # Only check the user with IDM again if it wasn't just created
        if not created and not validate_user_external_auth(user):
            return False

        request.user = user
        return True

    def challenge(self, request):
        if not request.external_auth_info:
            # Beware: this returns 401: Unauthorized, not 403: Forbidden
            # as the name implies.
            return rc.FORBIDDEN

        macaroon_bakery = _get_bakery(request)
        return _authorization_request(
            macaroon_bakery, auth_endpoint=request.external_auth_info.url,
            auth_domain=request.external_auth_info.domain)


class MacaroonDischargeRequest:
    """Return a Macaroon authentication request."""

    def __call__(self, request):
        if not request.external_auth_info:
            return HttpResponseNotFound('Not found')

        macaroon_bakery = _get_bakery(request)
        req_headers = request_headers(request)
        auth_checker = macaroon_bakery.checker.auth(
            httpbakery.extract_macaroons(req_headers))
        try:
            auth_info = auth_checker.allow(
                checkers.AuthContext(), [bakery.LOGIN_OP])
        except bakery.DischargeRequiredError as err:
            return _authorization_request(
                macaroon_bakery, derr=err, req_headers=req_headers)
        except bakery.VerificationError:
            return _authorization_request(
                macaroon_bakery, req_headers=req_headers,
                auth_endpoint=request.external_auth_info.url,
                auth_domain=request.external_auth_info.domain)
        except bakery.PermissionDenied:
            return HttpResponseForbidden()

        # a user is always returned since the authentication middleware creates
        # one if not found
        user = authenticate(request, identity=auth_info.identity)
        login(
            request, user,
            backend='maasserver.macaroon_auth.MacaroonAuthorizationBackend')
        return JsonResponse({'id': user.id, 'username': user.username})


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


class APIError(Exception):
    """IDMClient API error."""

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


class IDMClient:
    """A client for IDM agent API."""

    _url = None

    def __init__(self):
        auth_info = self._get_auth_info()
        self._client = httpbakery.Client(
            interaction_methods=[AgentInteractor(auth_info)])

    def get_groups(self, username):
        """Return a list of names fro groups a user belongs to."""
        url = self._get_url() + quote('/v1/u/{}/groups'.format(username))
        return self._request('GET', url)

    def _request(self, method, url):
        cookiejar = self._client.cookies
        resp = requests.request(
            method, url, cookies=cookiejar, auth=self._client.auth())
        # update cookies from the response
        for cookie in resp.cookies:
            cookiejar.set_cookie(cookie)

        content = resp.json()
        if resp.status_code != 200:
            raise APIError(resp.status_code, content.get('message'))
        return content

    def _get_auth_info(self):
        key = bakery.PrivateKey.deserialize(
            Config.objects.get_config('external_auth_key'))
        agent = Agent(
            url=self._get_url(),
            username=Config.objects.get_config('external_auth_user'))
        return AuthInfo(key=key, agents=[agent])

    def _get_url(self):
        if not self._url:
            self._url = Config.objects.get_config('external_auth_url')
        return self._url


def validate_user_external_auth(user, now=datetime.utcnow, client=None):
    """Check if a user is authenticated on IDM.

    If the IDM_USER_CHECK_INTERVAL has passed since the last check, the user is
    checked again.
    Its is_active status is changed based on the result of the check.

    """
    if user.username in SYSTEM_USERS:
        # don't perform the check for system users
        return True

    now = now()
    profile = user.userprofile
    if profile.auth_last_check + IDM_USER_CHECK_INTERVAL > now:
        return True

    if client is None:
        client = IDMClient()

    profile.auth_last_check = now
    profile.save()

    active = True
    try:
        # don't look at groups for now, we just care that the user is there
        # (IOW the call doesn't fail)
        client.get_groups(user.username)
    except APIError as error:
        active = False

    if active ^ user.is_active:
        user.is_active = active
        user.save()
    return active


class _IDClient(bakery.IdentityClient):

    def __init__(self, auth_endpoint, auth_domain=None):
        self.auth_endpoint = auth_endpoint
        self.auth_domain = auth_domain

    def declared_identity(self, ctx, declared):
        username = declared.get('username')
        if username is None:
            raise bakery.IdentityError('No username found')
        return bakery.SimpleIdentity(user=username)

    def identity_from_context(self, ctx):
        return None, [
            _get_authentication_caveat(
                self.auth_endpoint, domain=self.auth_domain)]


def _get_bakery(request):
    auth_endpoint = request.external_auth_info.url
    auth_domain = request.external_auth_info.domain
    return bakery.Bakery(
        key=_get_macaroon_oven_key(),
        root_key_store=KeyStore(MACAROON_LIFESPAN),
        location=request.build_absolute_uri('/'),
        locator=httpbakery.ThirdPartyLocator(
            allow_insecure=not auth_endpoint.startswith('https:')),
        identity_client=_IDClient(auth_endpoint, auth_domain=auth_domain),
        authorizer=bakery.ACLAuthorizer(
            get_acl=lambda ctx, op: [bakery.EVERYONE]))


def _authorization_request(bakery, derr=None, auth_endpoint=None,
                           auth_domain=None, req_headers=None):
    """Return a 401 response with a macaroon discharge request.

    Either `derr` or `auth_endpoint` must be specified.

    """
    bakery_version = httpbakery.request_version(req_headers or {})
    if derr:
        caveats, ops = derr.cavs(), derr.ops()
    else:
        caveats, ops = _get_macaroon_caveats_ops(auth_endpoint, auth_domain)
    expiration = datetime.utcnow() + MACAROON_LIFESPAN
    macaroon = bakery.oven.macaroon(bakery_version, expiration, caveats, ops)
    content, headers = httpbakery.discharge_required_response(
        macaroon, '/', 'maas')
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


def _get_macaroon_caveats_ops(auth_endpoint, auth_domain):
    """Return a 2-tuple with lists of caveats and operations for a macaroon."""
    caveats = [_get_authentication_caveat(auth_endpoint, domain=auth_domain)]
    ops = [bakery.LOGIN_OP]
    return caveats, ops


def _get_authentication_caveat(location, domain=''):
    """Return a Caveat requiring the user to be authenticated."""
    condition = 'is-authenticated-user'
    if domain:
        condition += ' @' + domain
    return checkers.Caveat(condition, location=location)
