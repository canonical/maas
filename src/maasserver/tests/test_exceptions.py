# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the exceptions module."""


import http.client
import json

from django.conf import settings

from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
    Redirect,
)
from maasserver.testing import extract_redirect
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestExceptions(MAASTestCase):
    def test_MAASAPIException_produces_http_response(self):
        error = factory.make_string()
        exception = MAASAPIBadRequest(error)
        response = exception.make_http_response()
        self.assertEqual(
            (http.client.BAD_REQUEST, error),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

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
            (http.client.BAD_REQUEST, error),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_returns_textual_response_if_message_is_a_string(self):
        error = factory.make_string()
        exception = MAASAPIValidationError(error)
        response = exception.make_http_response()
        self.assertEqual(
            "text/plain; charset=%s" % settings.DEFAULT_CHARSET,
            response.get("Content-Type"),
        )

    def test_returns_json_response_if_message_is_a_list(self):
        errors = [factory.make_string(), factory.make_string()]
        exception = MAASAPIValidationError(errors)
        response = exception.make_http_response()
        self.assertEqual(
            response.get("Content-Type"),
            f"application/json; charset={settings.DEFAULT_CHARSET}",
        )
        self.assertEqual(
            response.content.decode(settings.DEFAULT_CHARSET),
            json.dumps(errors),
        )

    def test_if_message_is_single_item_list_returns_only_first_message(self):
        errors = [factory.make_string()]
        exception = MAASAPIValidationError(errors)
        response = exception.make_http_response()
        self.assertEqual(
            response.get("Content-Type"),
            f"text/plain; charset={settings.DEFAULT_CHARSET}",
        )
        self.assertEqual(
            response.content.decode(settings.DEFAULT_CHARSET),
            errors[0],
        )

    def test_returns_json_response_if_message_is_a_dict(self):
        errors = {
            "error_1": [factory.make_string()],
            "error_2": [factory.make_string()],
        }
        exception = MAASAPIValidationError(errors)
        response = exception.make_http_response()
        self.assertEqual(
            response.get("Content-Type"),
            f"application/json; charset={settings.DEFAULT_CHARSET}",
        )
        self.assertEqual(
            response.content.decode(settings.DEFAULT_CHARSET),
            json.dumps(errors),
        )
