# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the snippets-related support routines for commissioning user data."""

import os.path

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from metadataserver.user_data.snippets import (
    get_snippet_context,
    is_snippet,
    list_snippets,
    read_snippet,
    strip_name,
)


class TestSnippets(MAASTestCase):
    def test_read_snippet_reads_snippet_file(self):
        contents = factory.make_string()
        snippet = self.make_file(contents=contents)
        self.assertEqual(
            contents,
            read_snippet(os.path.dirname(snippet), os.path.basename(snippet)),
        )

    def test_strip_name_leaves_simple_names_intact(self):
        simple_name = factory.make_string()
        self.assertEqual(simple_name, strip_name(simple_name))

    def test_strip_name_replaces_dots(self):
        self.assertEqual("_x_y_", strip_name(".x.y."))

    def test_is_snippet(self):
        are_snippets = {
            "snippet": True,
            "with-dash": True,
            "module.py": True,
            ".backup": False,
            "backup~": False,
            "module.pyc": False,
            "__init__.pyc": False,
            "tests": False,
        }
        self.assertEqual(
            are_snippets, {name: is_snippet(name) for name in are_snippets}
        )

    def test_list_snippets(self):
        snippets_dir = self.make_dir()
        factory.make_file(snippets_dir, "snippet")
        factory.make_file(snippets_dir, ".backup.pyc")
        self.assertEqual(["snippet"], list_snippets(snippets_dir))

    def test_get_snippet_context(self):
        contents = factory.make_string()
        snippets_dir = self.make_dir()
        factory.make_file(snippets_dir, "snippet.py", contents=contents)
        snippets = get_snippet_context(snippets_dir=snippets_dir)
        self.assertEqual({"base_user_data_sh", "snippet_py"}, snippets.keys())
        self.assertEqual(contents, snippets["snippet_py"])

    def test_get_snippet_always_contains_base_user_data(self):
        snippets_dir = self.make_dir()
        self.assertEqual(
            {"base_user_data_sh"},
            get_snippet_context(snippets_dir=snippets_dir).keys(),
        )
