# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the exceptions module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import httplib

from maasserver.exceptions import (
    MAASAPIBadRequest,
    Redirect,
    )
from maastesting.factory import factory
from maastesting.testcase import TestCase


class TestExceptions(TestCase):

    def test_MAASAPIException_produces_http_response(self):
        error = factory.getRandomString()
        exception = MAASAPIBadRequest(error)
        response = exception.make_http_response()
        self.assertEqual(
            (httplib.BAD_REQUEST, error),
            (response.status_code, response.content))

    def test_Redirect_produces_redirect_to_given_URL(self):
        target = factory.getRandomString()
        exception = Redirect(target)
        response = exception.make_http_response()
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(target, response['Location'])
