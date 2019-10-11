# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test combo view."""

__all__ = []

import http.client
import os

from django.conf import settings
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.django_urls import reverse
from maasserver.views.combo import get_absolute_location, MERGE_VIEWS
from maastesting.fixtures import ImportErrorFixture


class TestUtilities(MAASServerTestCase):
    def test_get_abs_location_returns_absolute_location_if_not_None(self):
        abs_location = "%s%s" % (os.path.sep, factory.make_string())
        self.assertEqual(
            abs_location, get_absolute_location(location=abs_location)
        )

    def test_get_abs_location_returns_rel_loc_if_not_in_dev_environment(self):
        self.useFixture(ImportErrorFixture("maastesting", "root"))
        static_root = factory.make_string()
        self.patch(settings, "STATIC_ROOT", static_root)
        rel_location = os.path.join(
            factory.make_string(), factory.make_string()
        )
        expected_location = os.path.join(static_root, rel_location)
        observed = get_absolute_location(location=rel_location)
        self.assertEqual(expected_location, observed)

    def test_get_abs_location_returns_rel_loc_if_in_dev_environment(self):
        rel_location = os.path.join(
            factory.make_string(), factory.make_string()
        )
        rel_location_base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "static",
        )
        expected_location = os.path.join(rel_location_base, rel_location)
        self.assertEqual(
            expected_location, get_absolute_location(location=rel_location)
        )


# String used by convoy to replace missing files.
CONVOY_MISSING_FILE = b"/* [missing] */"


class TestMergeLoaderView(MAASServerTestCase):
    """Test merge loader views."""

    def test_loads_all_views_correctly(self):
        for filename, merge_info in MERGE_VIEWS.items():
            url = reverse("merge", args=[filename])
            response = self.client.get(url)
            self.assertEqual(
                merge_info["content_type"],
                response["Content-Type"],
                "Content-type for %s does not match." % filename,
            )

            # Has all required files.
            for requested_file in merge_info["files"]:
                self.assertIn(
                    requested_file,
                    response.content.decode(settings.DEFAULT_CHARSET),
                )

            # No sign of a missing js file.
            self.assertNotIn(
                CONVOY_MISSING_FILE,
                response.content.decode(settings.DEFAULT_CHARSET),
            )

    def test_load_unknown_returns_302_blocked_by_middleware(self):
        response = self.client.get(reverse("merge", args=["unknown.js"]))
        self.assertEqual(http.client.FOUND, response.status_code)
