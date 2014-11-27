# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the exceptions module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib

from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
    Redirect,
    )
from maasserver.testing import extract_redirect
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
import simplejson as json
from testtools.matchers import Equals


class TestExceptions(MAASTestCase):

    def test_MAASAPIException_produces_http_response(self):
        error = factory.make_string()
        exception = MAASAPIBadRequest(error)
        response = exception.make_http_response()
        self.assertEqual(
            (httplib.BAD_REQUEST, error),
            (response.status_code, response.content))

    def test_Redirect_produces_redirect_to_given_URL(self):
        target = factory.make_string()
        exception = Redirect(target)
        response = exception.make_http_response()
        self.assertEqual(target, extract_redirect(response))


class TestMAASAPIValidationError(MAASTestCase):
    """Tests for the `MAASAPIValidationError` exception class."""

    def test_returns_http_response(self):
        error = factory.make_string()
        exception = MAASAPIValidationError(error)
        response = exception.make_http_response()
        self.assertEqual(
            (httplib.BAD_REQUEST, error),
            (response.status_code, response.content))

    def test_returns_textual_response_if_message_is_a_string(self):
        error = factory.make_string()
        exception = MAASAPIValidationError(error)
        response = exception.make_http_response()
        self.assertEqual(
            "text/plain; charset=utf-8", response.get("Content-Type"))

    def test_returns_json_response_if_message_is_a_list(self):
        errors = [
            factory.make_string(),
            factory.make_string(),
            ]
        exception = MAASAPIValidationError(errors)
        response = exception.make_http_response()
        self.expectThat(
            response.get("Content-Type"),
            Equals("application/json; charset=utf-8"))
        self.expectThat(response.content, Equals(json.dumps(errors)))

    def test_if_message_is_single_item_list_returns_only_first_message(self):
        errors = [
            factory.make_string(),
            ]
        exception = MAASAPIValidationError(errors)
        response = exception.make_http_response()
        self.expectThat(
            response.get("Content-Type"),
            Equals("text/plain; charset=utf-8"))
        self.expectThat(response.content, Equals(errors[0]))

    def test_returns_json_response_if_message_is_a_dict(self):
        errors = {
            'error_1': [factory.make_string()],
            'error_2': [factory.make_string()],
            }
        exception = MAASAPIValidationError(errors)
        response = exception.make_http_response()
        self.expectThat(
            response.get("Content-Type"),
            Equals("application/json; charset=utf-8"))
        self.expectThat(response.content, Equals(json.dumps(errors)))
