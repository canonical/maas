# Copyright 2018-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Backend for Macaroon-based authentication."""

from collections import namedtuple
from datetime import datetime, timedelta, timezone
from functools import partial
import os
from urllib.parse import quote

from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    JsonResponse,
)
from macaroonbakery import bakery, checkers, httpbakery
from macaroonbakery._utils import visit_page_with_browser
from macaroonbakery.httpbakery.agent import AgentInteractor
from piston3.utils import rc
import requests

from maasserver.auth import MAASAuthorizationBackend
from maasserver.macaroons import _get_macaroon_caveats_ops
from maasserver.models.user import SYSTEM_USERS
from maasserver.sqlalchemy import service_layer, ServiceLayerAdapter
from maasserver.utils.views import request_headers
from maasservicelayer.auth.external_auth import ExternalAuthType

MACAROON_LIFESPAN = timedelta(days=1)

EXTERNAL_USER_CHECK_INTERVAL = timedelta(hours=1)


def external_auth_enabled() -> bool:
    """Return whether external auth is enabled."""
    from maasserver.secrets import SecretManager

    config = SecretManager().get_composite_secret("external-auth", default={})
    return bool(config.get("url") or config.get("rbac-url"))


class MacaroonAuthorizationBackend(MAASAuthorizationBackend):
    """An authorization backend getting the user from macaroon identity."""

    def authenticate(self, request, identity=None):
        external_auth_info = request.external_auth_info
        if not external_auth_info or not identity:
            return

        username = identity.id()
        try:
            user = User.objects.get(username=username)
            if username not in SYSTEM_USERS and user.userprofile.is_local:
                return
        except User.DoesNotExist:
            user = User(username=username)
            user.save()

        if not user.is_active:
            # the user was previously marked as inactive, but is now
            # authenticated from external source, so it should be reactivated
            user.is_active = True
            user.save()

        if not validate_user_external_auth(
            user, external_auth_info, force_check=True
        ):
            return

        return user


class MacaroonAPIAuthentication:
    """A Piston authentication backend using macaroons."""

    def is_authenticated(self, request):
        if not request.external_auth_info:
            return False

        req_headers = request_headers(request)
        macaroon_bakery = service_layer.services.external_auth.get_bakery(
            request.build_absolute_uri("/")
        )
        auth_checker = macaroon_bakery.checker.auth(
            httpbakery.extract_macaroons(req_headers)
        )

        try:
            auth_info = service_layer.exec_async(
                auth_checker.allow(checkers.AuthContext(), [bakery.LOGIN_OP])
            )
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
        except User.DoesNotExist:
            user = User(username=username)
            user.save()

        # TODO: Replace with service layer
        if not validate_user_external_auth(user, request.external_auth_info):
            return False

        request.user = user
        return True

    def challenge(self, request):
        if not request.external_auth_info:
            # Beware: this returns 401: Unauthorized, not 403: Forbidden
            # as the name implies.
            return rc.FORBIDDEN

        macaroon_bakery = service_layer.services.external_auth.get_bakery(
            request.build_absolute_uri("/")
        )
        return _authorization_request(
            macaroon_bakery,
            auth_endpoint=request.external_auth_info.url,
            auth_domain=request.external_auth_info.domain,
        )


class MacaroonDischargeRequest:
    """Return a Macaroon authentication request."""

    def __call__(self, request):
        if not request.external_auth_info:
            return HttpResponseNotFound("Not found")

        macaroon_bakery = service_layer.services.external_auth.get_bakery(
            request.build_absolute_uri("/")
        )
        req_headers = request_headers(request)
        auth_checker = macaroon_bakery.checker.auth(
            httpbakery.extract_macaroons(req_headers)
        )

        try:
            auth_info = service_layer.exec_async(
                auth_checker.allow(checkers.AuthContext(), [bakery.LOGIN_OP])
            )
        except bakery.DischargeRequiredError as err:
            return _authorization_request(
                macaroon_bakery,
                derr=err,
                req_headers=req_headers,
            )
        except bakery.VerificationError:
            return _authorization_request(
                macaroon_bakery,
                req_headers=req_headers,
                auth_endpoint=request.external_auth_info.url,
                auth_domain=request.external_auth_info.domain,
            )
        except bakery.PermissionDenied:
            return HttpResponseForbidden()

        user = authenticate(request, identity=auth_info.identity)
        if user is None:
            # macaroon authentication can return None if the user exists but
            # doesn't have permission to log in
            return HttpResponseForbidden("User login not allowed")

        login(
            request,
            user,
            backend="maasserver.macaroon_auth.MacaroonAuthorizationBackend",
        )
        return JsonResponse(
            {
                attr: getattr(user, attr)
                for attr in ("id", "username", "is_superuser")
            }
        )


class APIError(Exception):
    """A `MacaroonClient` API error."""

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


# Details about a user from the extenral authentication source
UserDetails = namedtuple("UserDetails", ["username", "fullname", "email"])


class MacaroonClient:
    """A base client for talking JSON with a macaroon based client."""

    def __init__(self, url, auth_info):
        self._url = url.rstrip("/")
        self._auth_info = auth_info
        self._client = _get_bakery_client(auth_info=auth_info)

    def get_user_details(self, username: str) -> UserDetails:
        """Return details about a user."""
        return UserDetails(username=username, fullname="", email="")

    def _request(self, method, url, json=None, status_code=200):
        cookiejar = self._client.cookies
        resp = requests.request(
            method, url, cookies=cookiejar, auth=self._client.auth(), json=json
        )
        # update cookies from the response
        for cookie in resp.cookies:
            cookiejar.set_cookie(cookie)

        content = resp.json()
        if resp.status_code != status_code:
            raise APIError(resp.status_code, content.get("message"))
        return content


class CandidClient(MacaroonClient):
    """A client for Candid agent API."""

    def __init__(self, auth_info=None):
        if auth_info is None:
            with ServiceLayerAdapter() as sl:
                # Do not use sqlalchemy.service_layer, we want to create/delete RBACClients multiple times within the same thread.
                auth_info = sl.services.external_auth.get_auth_info()
        url = auth_info.agents[0].url
        super().__init__(url, auth_info)

    def get_user_details(self, username: str) -> UserDetails:
        """Return details about a user."""
        url = self._url + quote(f"/v1/u/{username}")
        details = self._request("GET", url)
        return UserDetails(
            username=details["username"],
            fullname=details.get("fullname", ""),
            email=details.get("email", ""),
        )

    def get_groups(self, username):
        """Return a list of names fro groups a user belongs to."""
        url = self._url + quote(f"/v1/u/{username}/groups")
        return self._request("GET", url)


class UserValidationFailed(Exception):
    """External user validation failed."""


def validate_user_external_auth(
    user,
    auth_info,
    now=partial(datetime.now, timezone.utc),  # noqa: B008
    candid_client=None,
    rbac_client=None,
    *,
    force_check=False,
):
    """Check if a user is authenticated with external auth.

    If the EXTERNAL_USER_CHECK_INTERVAL has passed since the last check, the
    user is checked again.  Its is_active status is changed based on the result
    of the check.

    """
    if user.username in SYSTEM_USERS:
        # don't perform the check for system users
        return True

    now = now()
    profile = user.userprofile
    no_check = (
        profile.auth_last_check
        and profile.auth_last_check + EXTERNAL_USER_CHECK_INTERVAL > now
    )
    if no_check and not force_check:
        return True

    profile.auth_last_check = now
    profile.save()

    active, superuser = False, False
    try:
        if auth_info.type == ExternalAuthType.CANDID:
            active, superuser, details = _validate_user_candid(
                auth_info, user.username, client=candid_client
            )
        elif auth_info.type == ExternalAuthType.RBAC:
            active, superuser, details = _validate_user_rbac(
                auth_info, user.username, client=rbac_client
            )
    except UserValidationFailed:
        return False

    if active ^ user.is_active:
        user.is_active = active
    user.is_superuser = superuser
    # update user details
    user.last_name = details.fullname
    user.email = details.email
    user.save()
    return active


def _validate_user_candid(auth_info, username, client=None):
    """Check if a user is active and/or superuser via Candid."""
    if client is None:
        client = CandidClient()

    try:
        groups = client.get_groups(username)
    except APIError:
        raise UserValidationFailed()  # noqa: B904

    if auth_info.admin_group:
        superuser = auth_info.admin_group in groups
    else:
        # if no admin group is specified, all users are admins
        superuser = True
    return True, superuser, client.get_user_details(username)


def _validate_user_rbac(auth_info, username, client=None):
    """Check if a user is active and/or superuser via RBAC."""
    if client is None:
        from maasserver.rbac import RBACClient

        client = RBACClient()

    try:
        is_admin = bool(
            client.allowed_for_user("maas", username, "admin")["admin"]
        )
        access_to_pools = any(
            client.allowed_for_user(
                "resource-pool",
                username,
                "view",
                "view-all",
                "deploy-machines",
                "admin-machines",
            ).values()
        )
        user_details = client.get_user_details(username)
    except APIError:
        raise UserValidationFailed()  # noqa: B904

    return (is_admin or access_to_pools, is_admin, user_details)


def _get_bakery_client(auth_info=None):
    """Return an httpbakery.Client."""
    if auth_info is not None:
        interactor = AgentInteractor(auth_info)
    else:
        interactor = httpbakery.WebBrowserInteractor(
            open=_candid_login(os.environ.get("MAAS_CANDID_CREDENTIALS"))
        )
    return httpbakery.Client(interaction_methods=[interactor])


def _candid_login(credentials):
    username, password = None, None
    if credentials:
        user_pass = credentials.split(":", 1)
        if len(user_pass) == 2:
            username, password = user_pass
    if not (username and password):
        return visit_page_with_browser

    def login_with_credentials(visit_url):
        session = requests.Session()
        # get the page, as it redirects. If the 'Accept' header is
        # supported, JSON content with the list of available IDPS is
        # returned.
        resp = session.get(visit_url, headers={"Accept": "application/json"})
        assert resp.status_code == 200
        if resp.headers["Content-Type"] == "application/json":
            idps = resp.json()["idps"]
            if len(idps) > 1:
                raise RuntimeError(
                    "Multiple authentication backends available"
                )
            url = idps[0]["url"]
        else:
            # The redirected page is the login form
            url = resp.url
        session.post(url, data={"username": username, "password": password})

    return login_with_credentials


def _authorization_request(
    bakery,
    derr=None,
    auth_endpoint=None,
    auth_domain=None,
    req_headers=None,
):
    """Return a 401 response with a macaroon discharge request.

    Either `derr` or `auth_endpoint` must be specified.

    """
    bakery_version = httpbakery.request_version(req_headers or {})
    if derr:
        caveats, ops = derr.cavs(), derr.ops()
    else:
        caveats, ops = _get_macaroon_caveats_ops(auth_endpoint, auth_domain)
    expiration = datetime.now(timezone.utc) + MACAROON_LIFESPAN
    macaroon = service_layer.exec_async(
        bakery.oven.macaroon(bakery_version, expiration, caveats, ops)
    )
    content, headers = httpbakery.discharge_required_response(
        macaroon, "/", "maas"
    )
    response = HttpResponse(status=401, reason="Unauthorized", content=content)
    for key, value in headers.items():
        response[key] = value
    return response


def _get_macaroon_private_key() -> bakery.PrivateKey:
    """Return a private key to use for macaroon caveats signing.

    The key is read from secrets if found, otherwise a new one is created and
    saved.
    """
    from maasserver.secrets import SecretManager

    manager = SecretManager()
    material = manager.get_simple_secret("macaroon-key", default=None)
    if material:
        return bakery.PrivateKey.deserialize(material)

    key = bakery.generate_key()
    manager.set_simple_secret("macaroon-key", key.serialize().decode("ascii"))
    return key
