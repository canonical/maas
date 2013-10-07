# Copyright 2012-2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the snippets-related support routines for commissioning user data."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os.path

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from metadataserver.commissioning.snippets import (
    get_snippet_context,
    is_snippet,
    list_snippets,
    read_snippet,
    strip_name,
    )


class TestSnippets(MAASTestCase):

    def test_read_snippet_reads_snippet_file(self):
        contents = factory.getRandomString()
        snippet = self.make_file(contents=contents)
        self.assertEqual(
            contents,
            read_snippet(os.path.dirname(snippet), os.path.basename(snippet)))

    def test_strip_name_leaves_simple_names_intact(self):
        simple_name = factory.getRandomString()
        self.assertEqual(simple_name, strip_name(simple_name))

    def test_strip_name_replaces_dots(self):
        self.assertEqual('_x_y_', strip_name('.x.y.'))

    def test_is_snippet(self):
        are_snippets = {
            'snippet': True,
            'with-dash': True,
            'module.py': True,
            '.backup': False,
            'backup~': False,
            'module.pyc': False,
            '__init__.pyc': False,
        }
        self.assertEqual(
            are_snippets,
            {name: is_snippet(name) for name in are_snippets})

    def test_list_snippets(self):
        snippets_dir = self.make_dir()
        factory.make_file(snippets_dir, 'snippet')
        factory.make_file(snippets_dir, '.backup.pyc')
        self.assertItemsEqual(['snippet'], list_snippets(snippets_dir))

    def test_get_snippet_context(self):
        contents = factory.getRandomString()
        snippets_dir = self.make_dir()
        factory.make_file(snippets_dir, 'snippet.py', contents=contents)
        self.assertItemsEqual(
            {'snippet_py': contents},
            get_snippet_context(snippets_dir=snippets_dir))

    def test_get_snippet_context_empty_if_no_snippets(self):
        snippets_dir = self.make_dir()
        context = {}
        self.assertEqual(
            context, get_snippet_context(snippets_dir=snippets_dir))
