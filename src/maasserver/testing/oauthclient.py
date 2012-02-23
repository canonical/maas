# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""OAuth client for API testing."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'OAuthAuthenticatedClient',
    ]

from time import time

from django.test.client import Client
from maasserver.models import get_auth_tokens
from oauth.oauth import (
    generate_nonce,
    OAuthConsumer,
    OAuthRequest,
    OAuthSignatureMethod_PLAINTEXT,
    OAuthToken,
    )


class OAuthAuthenticatedClient(Client):
    """OAuth-authenticated client for Piston API testing.
    """

    def __init__(self, user, token=None):
        """Initialize an oauth-authenticated test client.

        :param user: The user to authenticate.
        :type user: django.contrib.auth.models.User
        :param token: Optional token to authenticate `user` with.  If
            no `token` is given, the user's first token will be used.
        :type token: oauth.oauth.OAuthToken
        """
        super(OAuthAuthenticatedClient, self).__init__()
        if token is None:
            # Get the user's first token.
            token = get_auth_tokens(user)[0]
        assert token.user == user, "Token does not match User."
        consumer = token.consumer
        self.consumer = OAuthConsumer(str(consumer.key), str(consumer.secret))
        self.token = OAuthToken(str(token.key), str(token.secret))

    def _compose_auth_header(self, url):
        """Return additional header entries for request to `url`."""
        params = {
            'oauth_version': "1.0",
            'oauth_nonce': generate_nonce(),
            'oauth_timestamp': int(time()),
            'oauth_token': self.token.key,
            'oauth_consumer_key': self.consumer.key,
        }
        req = OAuthRequest(http_url=url, parameters=params)
        req.sign_request(
            OAuthSignatureMethod_PLAINTEXT(), self.consumer, self.token)
        header = req.to_header()
        # Django uses the 'HTTP_AUTHORIZATION' to look up Authorization
        # credentials.
        header['HTTP_AUTHORIZATION'] = header['Authorization']
        return header

    def _compose_url(self, path):
        """Put together a full URL for the resource at `path`."""
        environ = self._base_environ()
        return '%s://%s' % (environ['wsgi.url_scheme'], path)

    def request(self, **kwargs):
        url = self._compose_url(kwargs['PATH_INFO'])
        kwargs.update(self._compose_auth_header(url))
        return super(OAuthAuthenticatedClient, self).request(**kwargs)
