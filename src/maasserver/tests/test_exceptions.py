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
    InvalidConstraint,
    MAASAPIBadRequest,
    NoSuchConstraint,
    Redirect,
    )
from maasserver.testing import extract_redirect
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
        self.assertEqual(target, extract_redirect(response))

    def test_InvalidConstraint_is_bad_request(self):
        err = InvalidConstraint("height", "-1", ValueError("Not positive"))
        response = err.make_http_response()
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)

    def test_InvalidConstraint_str_without_context(self):
        err = InvalidConstraint("hue", "shiny")
        self.assertEqual(str(err), "Invalid 'hue' constraint 'shiny'")

    def test_InvalidConstraint_str_with_context(self):
        try:
            int("hundreds")
        except ValueError as e:
            context = e
        err = InvalidConstraint("limbs", "hundreds", context)
        self.assertEqual(str(err),
            "Invalid 'limbs' constraint 'hundreds': " + str(context))

    def test_NoSuchConstraint_str(self):
        err = NoSuchConstraint("hue")
        self.assertEqual(str(err), "No such 'hue' constraint")
