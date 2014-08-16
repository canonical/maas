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

    def test_OAuthUnauthorized_repr_include_original_failure_message(self):
        error_msg = factory.make_name('error-message')
        original_exception = oauth.OAuthError(error_msg)
        maas_exception = OAuthUnauthorized(original_exception)
        self.assertThat(
            unicode(maas_exception),
            Contains("Authorization Error: %r" % error_msg))
