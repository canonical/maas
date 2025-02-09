# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS-specific test HTTP clients."""

from time import time

from django.conf import settings
from django.test.client import RequestFactory
from piston3.oauth import (
    generate_nonce,
    OAuthConsumer,
    OAuthRequest,
    OAuthSignatureMethod_PLAINTEXT,
    OAuthToken,
)

from maasserver.models.user import get_auth_tokens
from maasserver.utils.orm import post_commit_hooks, transactional
from maastesting.djangoclient import SensibleClient
from maastesting.factory import factory


class MAASSensibleGetPathMixin:
    """A mixin that modifies `_get_path`.

    This simulates the twisted WSGI handler that is used by MAAS.
    """

    def _get_path(self, parsed):
        # FORCE_SCRIPT_NAME will cause this client to prepend the setting
        # to the front again when its passed to the WSGIRequest. In a running
        # FORCE_SCRIPT_NAME is removed by the twisted Resource and passed as
        # the SCRIPT_NAME in the environ. We perform the same behaviour here
        # by removing the initial FORCE_SCRIPT_NAME from the url path. The
        # WSGIRequest will add it back on just like in a running MAAS.
        script_path = settings.FORCE_SCRIPT_NAME.rstrip("/")
        if parsed.path.startswith(script_path):
            parsed = parsed._replace(path=parsed.path[len(script_path) :])
        return super()._get_path(parsed)


class MAASSensibleRequestFactory(MAASSensibleGetPathMixin, RequestFactory):
    """A derivative of Django's request factory specially for MAAS."""


class MAASSensibleClient(MAASSensibleGetPathMixin, SensibleClient):
    """A derivative of Django's test client specially for MAAS.

    This ensures that requests are performed in a transaction, and that
    post-commit hooks are alway fired or reset.

    It also permits logging-in using just a user object. A password will be
    configured and used to log-in.
    """

    def request(self, **request):
        # Make sure that requests are done within a transaction. Some kinds of
        # tests will already have a transaction in progress, in which case
        # this will act like a sub-transaction, but that's fine.
        upcall = transactional(super().request)
        # If we're outside of a transaction right now then the transactional()
        # wrapper above will ensure that post-commit hooks are run or reset on
        # return from the request. However, we want to ensure that post-commit
        # hooks are fired in any case, hence the belt-n-braces context.
        with post_commit_hooks:
            return upcall(**request)

    @transactional
    def login(self, *, user=None, **credentials):
        if user is None:
            return super().login(**credentials)
        elif user.is_anonymous:
            self.logout()
            return False
        else:
            credentials["password"] = password = factory.make_string()
            credentials["username"] = user.username
            user.set_password(password)
            user.save()
            return super().login(**credentials)


class MAASSensibleOAuthClient(MAASSensibleClient):
    """OAuth-authenticated client for Piston API testing."""

    def __init__(self, user=None, token=None):
        """Initialize an oauth-authenticated test client.

        :param user: The user to authenticate.
        :type user: django.contrib.auth.models.User
        :param token: Optional token to authenticate `user` with.  If
            no `token` is given, the user's first token will be used.
        :type token: oauth.oauth.OAuthToken
        """
        super().__init__()
        if user is not None or token is not None:
            self.login(user=user, token=token)
        else:
            self.logout()

    def login(self, *, user=None, token=None):
        """Override Django's `Client.login`."""
        if user is None:
            assert token is not None
            return self._token_set(token)
        else:
            if user.is_anonymous:
                self._token_clear()
                return False
            elif token is None:
                token = get_auth_tokens(user)[0]
                return self._token_set(token)
            else:
                assert token.user == user
                return self._token_set(token)

    def logout(self):
        """Override Django's `Client.logout`."""
        self._token_clear()

    def _token_set(self, token):
        consumer = token.consumer
        self.consumer = OAuthConsumer(consumer.key, consumer.secret)
        self.token = OAuthToken(token.key, token.secret)

    def _token_clear(self):
        self.consumer = None
        self.token = None

    def _compose_auth_header(self, url):
        """Return additional header entries for request to `url`."""
        params = {
            "oauth_version": "1.0",
            "oauth_nonce": generate_nonce(),
            "oauth_timestamp": int(time()),
            "oauth_token": self.token.key,
            "oauth_consumer_key": self.consumer.key,
        }
        req = OAuthRequest(http_url=url, parameters=params)
        req.sign_request(
            OAuthSignatureMethod_PLAINTEXT(), self.consumer, self.token
        )
        header = req.to_header()
        # Django uses the 'HTTP_AUTHORIZATION' to look up Authorization
        # credentials.
        header["HTTP_AUTHORIZATION"] = header["Authorization"]
        return header

    def _compose_url(self, path):
        """Put together a full URL for the resource at `path`."""
        environ = self._base_environ()
        return "{}://{}".format(environ["wsgi.url_scheme"], path)

    def request(self, **kwargs):
        url = self._compose_url(kwargs["PATH_INFO"])
        if self.consumer is not None:
            kwargs.update(self._compose_auth_header(url))
        return super().request(**kwargs)
