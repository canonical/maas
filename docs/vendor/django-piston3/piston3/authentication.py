import base64
import binascii

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import (
    AnonymousUser,
    User,
)
from django.core.exceptions import ImproperlyConfigured
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
)
from django.shortcuts import render
from django.template import loader
from django.urls import get_callable

from . import (
    forms,
    oauth,
)


class NoAuthentication:
    """
    Authentication handler that always returns
    True, so no authentication is needed, nor
    initiated (`challenge` is missing.)
    """

    def is_authenticated(self, request):
        return True


class HttpBasicAuthentication:
    """
    Basic HTTP authenticater. Synopsis:

    Authentication handlers must implement two methods:
     - `is_authenticated`: Will be called when checking for
        authentication. Receives a `request` object, please
        set your `User` object on `request.user`, otherwise
        return False (or something that evaluates to False.)
     - `challenge`: In cases where `is_authenticated` returns
        False, the result of this method will be returned.
        This will usually be a `HttpResponse` object with
        some kind of challenge headers and 401 code on it.
    """

    def __init__(self, auth_func=authenticate, realm="API"):
        self.auth_func = auth_func
        self.realm = realm

    def is_authenticated(self, request):
        auth_string = request.META.get("HTTP_AUTHORIZATION", None)

        if not auth_string:
            return False

        try:
            (authmeth, auth) = auth_string.split(" ", 1)

            if not authmeth.lower() == "basic":
                return False

            auth = auth.encode("ascii")  # base64 only operates on bytes
            auth = base64.decodebytes(auth.strip())
            auth = auth.decode("ascii")
            (username, password) = auth.split(":", 1)
        except (ValueError, binascii.Error):
            return False

        request.user = (
            self.auth_func(username=username, password=password)
            or AnonymousUser()
        )

        return request.user not in (False, None, AnonymousUser())

    def challenge(self, request):
        resp = HttpResponse("Authorization Required")
        resp["WWW-Authenticate"] = f'Basic realm="{self.realm}"'
        resp.status_code = 401
        return resp

    def __repr__(self):
        return f"<HTTPBasic: realm={self.realm}>"


class HttpBasicSimple(HttpBasicAuthentication):
    def __init__(self, realm, username, password):
        self.user = User.objects.get(username=username)
        self.password = password

        super().__init__(auth_func=self.hash, realm=realm)

    def hash(self, username, password):
        if username == self.user.username and password == self.password:
            return self.user


def load_data_store():
    """Load data store for OAuth Consumers, Tokens, Nonces and Resources"""
    path = getattr(settings, "OAUTH_DATA_STORE", "piston3.store.DataStore")

    # stolen from django.contrib.auth.load_backend
    i = path.rfind(".")
    module, attr = path[:i], path[i + 1 :]

    try:
        mod = __import__(module, {}, {}, attr)
    except ImportError as e:
        raise ImproperlyConfigured(
            f'Error importing OAuth data store {module}: "{e}"'
        )

    try:
        cls = getattr(mod, attr)
    except AttributeError:
        raise ImproperlyConfigured(
            f'Module {module} does not define a "{attr}" OAuth data store'
        )

    return cls


# Set the datastore here.
oauth_datastore = load_data_store()


def initialize_server_request(request):
    """
    Shortcut for initialization.
    """
    if request.method == "POST":
        params = dict(request.POST.items())
    else:
        params = {}

    # Seems that we want to put HTTP_AUTHORIZATION into 'Authorization'
    # for oauth.py to understand. Lovely.
    request.META["Authorization"] = request.META.get("HTTP_AUTHORIZATION", "")

    oauth_request = oauth.OAuthRequest.from_request(
        request.method,
        request.build_absolute_uri(),
        headers=request.META,
        parameters=params,
        query_string=request.environ.get("QUERY_STRING", ""),
    )

    if oauth_request:
        oauth_server = oauth.OAuthServer(oauth_datastore(oauth_request))
        oauth_server.add_signature_method(
            oauth.OAuthSignatureMethod_PLAINTEXT()
        )
        oauth_server.add_signature_method(
            oauth.OAuthSignatureMethod_HMAC_SHA1()
        )
    else:
        oauth_server = None

    return oauth_server, oauth_request


def send_oauth_error(err=None):
    """
    Shortcut for sending an error.
    """
    response = HttpResponse(err.message.encode("utf-8"))
    response.status_code = 401

    realm = "OAuth"
    header = oauth.build_authenticate_header(realm=realm)

    for k, v in header.items():
        response[k] = v

    return response


def oauth_request_token(request):
    oauth_server, oauth_request = initialize_server_request(request)

    if oauth_server is None:
        return INVALID_PARAMS_RESPONSE
    try:
        token = oauth_server.fetch_request_token(oauth_request)

        response = HttpResponse(token.to_string())
    except oauth.OAuthError as err:
        response = send_oauth_error(err)

    return response


def oauth_auth_view(request, token, callback, params):
    form = forms.OAuthAuthenticationForm(
        initial={
            "oauth_token": token.key,
            "oauth_callback": token.get_callback_url() or callback,
        }
    )

    return render(request, "piston/authorize_token.html", {"form": form})


@login_required
def oauth_user_auth(request):
    oauth_server, oauth_request = initialize_server_request(request)

    if oauth_request is None:
        return INVALID_PARAMS_RESPONSE

    try:
        token = oauth_server.fetch_request_token(oauth_request)
    except oauth.OAuthError as err:
        return send_oauth_error(err)

    try:
        callback = oauth_server.get_callback(oauth_request)
    except Exception:
        callback = None

    if request.method == "GET":
        params = oauth_request.get_normalized_parameters()

        oauth_view = getattr(settings, "OAUTH_AUTH_VIEW", None)
        if oauth_view is None:
            return oauth_auth_view(request, token, callback, params)
        else:
            return get_callable(oauth_view)(request, token, callback, params)
    elif request.method == "POST":
        try:
            form = forms.OAuthAuthenticationForm(request.POST)
            if form.is_valid():
                token = oauth_server.authorize_token(token, request.user)
                args = "?" + token.to_string(only_key=True)
            else:
                args = "?error={}".format("Access not granted by user.")
                print("FORM ERROR", form.errors)

            if not callback:
                callback = getattr(settings, "OAUTH_CALLBACK_VIEW")
                return get_callable(callback)(request, token)

            response = HttpResponseRedirect(callback + args)

        except oauth.OAuthError as err:
            response = send_oauth_error(err)
    else:
        response = HttpResponse("Action not allowed.")

    return response


def oauth_access_token(request):
    oauth_server, oauth_request = initialize_server_request(request)

    if oauth_request is None:
        return INVALID_PARAMS_RESPONSE

    try:
        token = oauth_server.fetch_access_token(oauth_request)
        return HttpResponse(token.to_string())
    except oauth.OAuthError as err:
        return send_oauth_error(err)


INVALID_PARAMS_RESPONSE = send_oauth_error(
    oauth.OAuthError("Invalid request parameters.")
)


class OAuthAuthentication:
    """
    OAuth authentication. Based on work by Leah Culver.
    """

    def __init__(self, realm="API"):
        self.realm = realm
        self.builder = oauth.build_authenticate_header

    def is_authenticated(self, request):
        """
        Checks whether a means of specifying authentication
        is provided, and if so, if it is a valid token.

        Read the documentation on `HttpBasicAuthentication`
        for more information about what goes on here.
        """
        if self.is_valid_request(request):
            try:
                consumer, token, parameters = self.validate_token(request)
            except oauth.OAuthError as err:
                print(send_oauth_error(err))
                return False

            if consumer and token:
                request.user = token.user
                request.consumer = consumer
                request.throttle_extra = token.consumer.id
                return True

        return False

    def challenge(self, request):
        """
        Returns a 401 response with a small bit on
        what OAuth is, and where to learn more about it.

        When this was written, browsers did not understand
        OAuth authentication on the browser side, and hence
        the helpful template we render. Maybe some day in the
        future, browsers will take care of this stuff for us
        and understand the 401 with the realm we give it.
        """
        response = HttpResponse()
        response.status_code = 401
        realm = "API"

        for k, v in self.builder(realm=realm).items():
            response[k] = v

        tmpl = loader.render_to_string(
            "oauth/challenge.html", {"MEDIA_URL": settings.MEDIA_URL}
        )

        response.content = tmpl

        return response

    @staticmethod
    def is_valid_request(request):
        """
        Checks whether the required parameters are either in
        the http-authorization header sent by some clients,
        which is by the way the preferred method according to
        OAuth spec, but otherwise fall back to `GET` and `POST`.
        """
        must_have = [
            "oauth_" + s
            for s in [
                "consumer_key",
                "token",
                "signature",
                "signature_method",
                "timestamp",
                "nonce",
            ]
        ]

        def is_in(param):
            return all([(p in param) for p in must_have])

        auth_params = request.META.get("HTTP_AUTHORIZATION", "")
        get_params = request.GET
        post_params = request.POST

        return is_in(auth_params) or is_in(get_params) or is_in(post_params)

    @staticmethod
    def validate_token(request, check_timestamp=True, check_nonce=True):
        oauth_server, oauth_request = initialize_server_request(request)
        return oauth_server.verify_request(oauth_request)
