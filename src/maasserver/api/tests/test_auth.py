# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `api.auth` module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.api.auth import OAuthUnauthorized
from maasserver.testing.factory import factory
from maastesting.testcase import MAASTestCase
from oauth import oauth
from testtools.matchers import Contains


class TestOAuthUnauthorized(MAASTestCase):

    def test_exception_unicode_includes_original_failure_message(self):
        error_msg = factory.make_name('error-message')
        original_exception = oauth.OAuthError(error_msg)
        maas_exception = OAuthUnauthorized(original_exception)
        self.assertThat(
            unicode(maas_exception),
            Contains("Authorization Error: %r" % error_msg))

    def test_exception_unicode_includes_user_friendly_message(self):
        # When the error is an authentication error, the message is more
        # user-friendly than the default 'Invalid consumer.'.
        original_exception = oauth.OAuthError('Invalid consumer.')
        maas_exception = OAuthUnauthorized(original_exception)
        self.assertThat(
            unicode(maas_exception),
            Contains("Authorization Error: Invalid API key."))
