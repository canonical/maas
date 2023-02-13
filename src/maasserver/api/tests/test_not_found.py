# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the not found handler."""


import http.client

from django.conf import settings
from django.urls import reverse

from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


class TestNotFoundHandler(APITestCase.ForAnonymousAndUserAndAdmin):
    scenarios = (
        ("GET", dict(method="get")),
        ("POST", dict(method="post")),
        ("PUT", dict(method="put")),
        ("DELETE", dict(method="delete")),
    )

    def test_calling_bogus_handler_returns_not_found(self):
        # Use the nodes handler to get the API prefix right.
        handler_url = reverse("nodes_handler")
        # Add bogus path.
        handler_url += "/".join(factory.make_name("path") for _ in range(5))

        response = getattr(self.client, self.method)(handler_url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.assertEqual("text/plain; charset=utf-8", response["content-type"])
        self.assertEqual(
            "Unknown API endpoint: %s." % handler_url,
            response.content.decode(settings.DEFAULT_CHARSET),
        )
