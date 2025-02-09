# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `api.auth` module."""

from datetime import datetime, timedelta, timezone
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from piston3 import oauth

from maasserver.api import auth as api_auth
from maasserver.api.auth import (
    MAASAPIAuthentication,
    OAuthBadRequest,
    OAuthUnauthorized,
)
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasservicelayer.auth.external_auth import (
    ExternalAuthConfig,
    ExternalAuthType,
)
from maastesting.testcase import MAASTestCase
from metadataserver.nodeinituser import get_node_init_user


class TestMAASAPIAuthentication(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        SecretManager().set_composite_secret(
            "external-auth", {"url": "https://example.com"}
        )

    def make_request(self, user=None):
        request = factory.make_fake_request("/")
        request.user = user or AnonymousUser()

        auth_url = (
            SecretManager()
            .get_composite_secret("external-auth", default={})
            .get("url", "")
        )
        if auth_url:
            request.external_auth_info = ExternalAuthConfig(
                type=ExternalAuthType.CANDID,
                url=auth_url,
                domain="domain",
                admin_group="admins",
            )
        else:
            request.external_auth_info = None
        return request

    def test_is_authenticated(self):
        SecretManager().delete_secret("external-auth")
        user = factory.make_User()
        request = self.make_request(user=user)
        auth = MAASAPIAuthentication()
        self.assertTrue(auth.is_authenticated(request))

    def test_is_authenticated_external_auth(self):
        user = factory.make_User()
        request = self.make_request(user=user)
        auth = MAASAPIAuthentication()
        self.assertTrue(auth.is_authenticated(request))

    def test_is_authenticated_external_auth_validate_user(self):
        mock_validate = self.patch(api_auth, "validate_user_external_auth")
        mock_validate.return_value = True

        auth = MAASAPIAuthentication()
        user = factory.make_User()
        user.userprofile.auth_last_check = datetime.now(
            timezone.utc
        ) - timedelta(days=1)
        mock_token = mock.Mock(user=user)
        request = self.make_request()

        auth.is_valid_request = lambda request: True
        auth.validate_token = lambda request: (mock.Mock(), mock_token, None)
        self.assertTrue(auth.is_authenticated(request))
        mock_validate.assert_called_with(
            user,
            ExternalAuthConfig(
                ExternalAuthType.CANDID,
                "https://example.com",
                "domain",
                "admins",
            ),
        )

    def test_is_authenticated_external_auth_validate_fail(self):
        mock_validate = self.patch(api_auth, "validate_user_external_auth")
        mock_validate.return_value = False

        auth = MAASAPIAuthentication()
        user = factory.make_User()
        user.userprofile.auth_last_check = datetime.now(
            timezone.utc
        ) - timedelta(days=1)
        mock_token = mock.Mock(user=user)
        request = self.make_request()
        auth.is_valid_request = lambda request: True
        auth.validate_token = lambda request: (mock.Mock(), mock_token, None)
        self.assertFalse(auth.is_authenticated(request))
        # check interval not expired, the user isn't checked
        mock_validate.assert_called_with(
            user,
            ExternalAuthConfig(
                type=ExternalAuthType.CANDID,
                url="https://example.com",
                domain="domain",
                admin_group="admins",
            ),
        )

    def test_is_authenticated_external_auth_user_local(self):
        mock_validate = self.patch(api_auth, "validate_user_external_auth")
        mock_validate.return_value = True

        auth = MAASAPIAuthentication()
        user = factory.make_User()
        user.userprofile.is_local = True
        user.userprofile.save()
        request = self.make_request(user=user)
        self.assertFalse(auth.is_authenticated(request))
        mock_validate.assert_not_called()

    def test_is_authenticated_external_auth_system_user(self):
        mock_validate = self.patch(api_auth, "validate_user_external_auth")
        mock_validate.return_value = True

        auth = MAASAPIAuthentication()
        user = get_node_init_user()
        request = self.make_request()
        mock_token = mock.Mock(user=user)
        auth.is_valid_request = lambda request: True
        auth.validate_token = lambda request: (mock.Mock(), mock_token, None)
        self.assertTrue(auth.is_authenticated(request))
        mock_validate.assert_not_called()

    def test_is_authenticated_false_external_user_no_external_auth(self):
        SecretManager().delete_secret("external-auth")
        user = factory.make_User()
        user.userprofile.is_local = False
        user.userprofile.save()
        mock_token = mock.Mock(user=user)
        request = self.make_request()
        auth = MAASAPIAuthentication()
        auth.is_valid_request = lambda request: True
        auth.validate_token = lambda request: (mock.Mock(), mock_token, None)
        self.assertFalse(auth.is_authenticated(request))


class TestOAuthUnauthorized(MAASTestCase):
    def test_exception_unicode_includes_original_failure_message(self):
        error_msg = factory.make_name("error-message")
        original_exception = oauth.OAuthError(error_msg)
        maas_exception = OAuthUnauthorized(original_exception)
        self.assertIn(
            "Authorization Error: %r" % error_msg,
            str(maas_exception),
        )

    def test_exception_unicode_includes_user_friendly_message(self):
        # When the error is an authentication error, the message is more
        # user-friendly than the default 'Invalid consumer.'.
        original_exception = oauth.OAuthError("Invalid consumer.")
        maas_exception = OAuthUnauthorized(original_exception)
        self.assertIn(
            "Authorization Error: Invalid API key.",
            str(maas_exception),
        )


class TestOAuthBadRequest(MAASTestCase):
    def test_exception_unicode_includes_original_failure_message(self):
        error_msg = factory.make_name("error-message")
        original_exception = oauth.OAuthMissingParam(error_msg)
        maas_exception = OAuthBadRequest(original_exception)
        self.assertIn(
            f"Bad Request: {error_msg}",
            str(maas_exception),
        )
