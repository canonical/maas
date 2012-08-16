# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.testing`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import httplib

from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    )
from maasserver.testing import (
    extract_redirect,
    reload_object,
    reload_objects,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestModelTestCase
from maasserver.testing.tests.models import TestModel

# Horrible kludge.  Works around a bug where delete() does not work on
# test models when using nose.  Without this, running the tests in this
# module fails at the delete() calls, saying a table node_c does not
# exist.  (Running just the test case passes, but running the entire
# module's tests fails even if the failing test case is the only one).
#
# https://github.com/jbalogh/django-nose/issues/15
TestModel._meta.get_all_related_objects()


class TestHelpers(TestModelTestCase):
    """Test helper functions."""

    app = 'maasserver.testing.tests'

    def test_extract_redirect_extracts_redirect_location(self):
        url = factory.getRandomString()
        self.assertEqual(
            url, extract_redirect(HttpResponseRedirect(url)))

    def test_extract_redirect_only_returns_target_path(self):
        url_path = factory.getRandomString()
        self.assertEqual(
            "/%s" % url_path,
            extract_redirect(
                HttpResponseRedirect("http://example.com/%s" % url_path)))

    def test_extract_redirect_errors_out_helpfully_if_not_a_redirect(self):
        content = factory.getRandomString(10)
        other_response = HttpResponse(status=httplib.OK, content=content)
        try:
            extract_redirect(other_response)
        except ValueError as e:
            pass

        self.assertIn(unicode(httplib.OK), unicode(e))
        self.assertIn(content, unicode(e))

    def test_reload_object_reloads_object(self):
        test_obj = TestModel(text="old text")
        test_obj.save()
        TestModel.objects.filter(id=test_obj.id).update(text="new text")
        self.assertEqual("new text", reload_object(test_obj).text)

    def test_reload_object_returns_None_for_deleted_object(self):
        test_obj = TestModel()
        test_obj.save()
        TestModel.objects.filter(id=test_obj.id).delete()
        self.assertIsNone(reload_object(test_obj))

    def test_reload_objects_reloads_objects(self):
        texts = ['1 text', '2 text', '3 text']
        objs = [TestModel(text=text) for text in texts]
        for obj in objs:
            obj.save()
        texts[0] = "different text"
        TestModel.objects.filter(id=objs[0].id).update(text=texts[0])
        self.assertItemsEqual(
            texts, [obj.text for obj in reload_objects(TestModel, objs)])

    def test_reload_objects_omits_deleted_objects(self):
        objs = [TestModel() for counter in range(3)]
        for obj in objs:
            obj.save()
        dead_obj = objs.pop(0)
        TestModel.objects.filter(id=dead_obj.id).delete()
        self.assertItemsEqual(objs, reload_objects(TestModel, objs))
