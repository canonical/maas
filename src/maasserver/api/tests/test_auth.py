# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `api.auth` module."""

__all__ = []

from maasserver.api.auth import (
    MAASAPIAuthentication,
    OAuthUnauthorized,
)
from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.testcase import MAASTestCase
from oauth import oauth
from testtools.matchers import Contains


class TestMAASAPIAuthentication(MAASServerTestCase):

    def test_is_authenticated(self):
        user = factory.make_User()
        request = factory.make_fake_request('/')
        request.user = user
        auth = MAASAPIAuthentication()
        self.assertTrue(auth.is_authenticated(request))

    def test_is_authenticated_external_auth(self):
        Config.objects.set_config('external_auth_url', 'https://example.com')
        user = factory.make_User()
        request = factory.make_fake_request('/')
        request.user = user
        auth = MAASAPIAuthentication()
        self.assertTrue(auth.is_authenticated(request))


class TestOAuthUnauthorized(MAASTestCase):

    def test_exception_unicode_includes_original_failure_message(self):
        error_msg = factory.make_name('error-message')
        original_exception = oauth.OAuthError(error_msg)
        maas_exception = OAuthUnauthorized(original_exception)
        self.assertThat(
            str(maas_exception),
            Contains("Authorization Error: %r" % error_msg))

    def test_exception_unicode_includes_user_friendly_message(self):
        # When the error is an authentication error, the message is more
        # user-friendly than the default 'Invalid consumer.'.
        original_exception = oauth.OAuthError('Invalid consumer.')
        maas_exception = OAuthUnauthorized(original_exception)
        self.assertThat(
            str(maas_exception),
            Contains("Authorization Error: Invalid API key."))
