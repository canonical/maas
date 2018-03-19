# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `api.auth` module."""

__all__ = []

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from maasserver.api.auth import (
    MAASAPIAuthentication,
    OAuthUnauthorized,
)
from maasserver.middleware import ExternalAuthInfo
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
        user = factory.make_User()
        request = factory.make_fake_request('/')
        request.external_auth_info = ExternalAuthInfo(
            'macaroon', 'https://example.com')
        request.user = user
        auth = MAASAPIAuthentication()
        self.assertTrue(auth.is_authenticated(request))

    @mock.patch('maasserver.api.auth.validate_user_external_auth')
    def test_is_authenticated_external_auth_validate_user(self, mock_validate):
        mock_validate.return_value = True

        auth = MAASAPIAuthentication()
        user = factory.make_User()
        user.userprofile.auth_last_check -= timedelta(days=1)
        mock_token = mock.Mock(user=user)
        request = factory.make_fake_request('/')
        request.external_auth_info = ExternalAuthInfo(
            'macaroon', 'https://example.com')
        request.user = AnonymousUser()
        auth.is_valid_request = lambda request: True
        auth.validate_token = lambda request: (mock.Mock(), mock_token, None)
        self.assertTrue(auth.is_authenticated(request))
        mock_validate.assert_called()

    @mock.patch('maasserver.api.auth.validate_user_external_auth')
    def test_is_authenticated_external_auth_validate_fail(self, mock_validate):
        mock_validate.return_value = False

        auth = MAASAPIAuthentication()
        user = factory.make_User()
        user.userprofile.auth_last_check -= timedelta(days=1)
        mock_token = mock.Mock(user=user)
        request = factory.make_fake_request('/')
        request.external_auth_info = ExternalAuthInfo(
            'macaroon', 'https://example.com')
        request.user = AnonymousUser()
        auth.is_valid_request = lambda request: True
        auth.validate_token = lambda request: (mock.Mock(), mock_token, None)
        self.assertFalse(auth.is_authenticated(request))
        # check interval not expired, the user isn't checked
        mock_validate.assert_called()


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
