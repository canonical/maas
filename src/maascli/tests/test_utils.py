# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli.utils`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maascli import utils
from maastesting.testcase import MAASTestCase
from testtools.matchers import (
    AfterPreprocessing,
    Equals,
    MatchesListwise,
    )


class TestDocstringParsing(MAASTestCase):
    """Tests for docstring parsing in `maascli.utils`."""

    def test_basic(self):
        self.assertEqual(
            ("Title", "Body"),
            utils.parse_docstring("Title\n\nBody"))
        self.assertEqual(
            ("A longer title", "A longer body"),
            utils.parse_docstring(
                "A longer title\n\nA longer body"))

    def test_no_body(self):
        # parse_docstring returns an empty string when there's no body.
        self.assertEqual(
            ("Title", ""),
            utils.parse_docstring("Title\n\n"))
        self.assertEqual(
            ("Title", ""),
            utils.parse_docstring("Title"))

    def test_unwrapping(self):
        # parse_docstring unwraps the title paragraph, and dedents the body
        # paragraphs.
        self.assertEqual(
            ("Title over two lines",
             "Paragraph over\ntwo lines\n\n"
             "Another paragraph\nover two lines"),
            utils.parse_docstring("""
                Title over
                two lines

                Paragraph over
                two lines

                Another paragraph
                over two lines
                """))

    def test_gets_docstring_from_function(self):
        # parse_docstring can extract the docstring when the argument passed
        # is not a string type.
        def example():
            """Title.

            Body.
            """
        self.assertEqual(
            ("Title.", "Body."),
            utils.parse_docstring(example))

    def test_normalises_whitespace(self):
        # parse_docstring can parse CRLF/CR/LF text, but always emits LF (\n,
        # new-line) separated text.
        self.assertEqual(
            ("long title", ""),
            utils.parse_docstring("long\r\ntitle"))
        self.assertEqual(
            ("title", "body1\n\nbody2"),
            utils.parse_docstring("title\n\nbody1\r\rbody2"))


class TestFunctions(MAASTestCase):
    """Tests for miscellaneous functions in `maascli.utils`."""

    def test_safe_name(self):
        # safe_name attempts to discriminate parts of a vaguely camel-cased
        # string, and rejoins them using a hyphen.
        expected = {
            "NodeHandler": "Node-Handler",
            "SpadeDiggingHandler": "Spade-Digging-Handler",
            "SPADE_Digging_Handler": "SPADE-Digging-Handler",
            "SpadeHandlerForDigging": "Spade-Handler-For-Digging",
            "JamesBond007": "James-Bond007",
            "JamesBOND": "James-BOND",
            "James-BOND-007": "James-BOND-007",
            }
        observed = {
            name_in: utils.safe_name(name_in)
            for name_in in expected
            }
        self.assertItemsEqual(
            expected.items(), observed.items())

    def test_safe_name_non_ASCII(self):
        # safe_name will not break if passed a string with non-ASCII
        # characters. However, those characters will not be present in the
        # returned name.
        self.assertEqual(
            "a-b-c", utils.safe_name(u"a\u1234_b\u5432_c\u9876"))

    def test_safe_name_string_type(self):
        # Given a unicode string, safe_name will always return a unicode
        # string, and given a byte string it will always return a byte string.
        self.assertIsInstance(utils.safe_name(u"fred"), unicode)
        self.assertIsInstance(utils.safe_name(b"fred"), bytes)

    def test_handler_command_name(self):
        # handler_command_name attempts to discriminate parts of a vaguely
        # camel-cased string, removes any "handler" parts, joins again with
        # hyphens, and returns the whole lot in lower case.
        expected = {
            "NodeHandler": "node",
            "SpadeDiggingHandler": "spade-digging",
            "SPADE_Digging_Handler": "spade-digging",
            "SpadeHandlerForDigging": "spade-for-digging",
            "JamesBond007": "james-bond007",
            "JamesBOND": "james-bond",
            "James-BOND-007": "james-bond-007",
            }
        observed = {
            name_in: utils.handler_command_name(name_in)
            for name_in in expected
            }
        self.assertItemsEqual(
            expected.items(), observed.items())
        # handler_command_name also ensures that all names are encoded into
        # byte strings.
        expected_types = {
            name_out: bytes
            for name_out in observed.values()
            }
        observed_types = {
            name_out: type(name_out)
            for name_out in observed.values()
            }
        self.assertItemsEqual(
            expected_types.items(), observed_types.items())

    def test_handler_command_name_non_ASCII(self):
        # handler_command_name will not break if passed a string with
        # non-ASCII characters. However, those characters will not be present
        # in the returned name.
        self.assertEqual(
            "a-b-c", utils.handler_command_name(u"a\u1234_b\u5432_c\u9876"))

    def test_ensure_trailing_slash(self):
        # ensure_trailing_slash ensures that the given string - typically a
        # URL or path - has a trailing forward slash.
        self.assertEqual("fred/", utils.ensure_trailing_slash("fred"))
        self.assertEqual("fred/", utils.ensure_trailing_slash("fred/"))

    def test_ensure_trailing_slash_string_type(self):
        # Given a unicode string, ensure_trailing_slash will always return a
        # unicode string, and given a byte string it will always return a byte
        # string.
        self.assertIsInstance(utils.ensure_trailing_slash(u"fred"), unicode)
        self.assertIsInstance(utils.ensure_trailing_slash(b"fred"), bytes)

    def test_api_url(self):
        transformations = {
            "http://example.com/": "http://example.com/api/1.0/",
            "http://example.com/foo": "http://example.com/foo/api/1.0/",
            "http://example.com/foo/": "http://example.com/foo/api/1.0/",
            "http://example.com/api/7.9": "http://example.com/api/7.9/",
            "http://example.com/api/7.9/": "http://example.com/api/7.9/",
            }.items()
        urls = [url for url, url_out in transformations]
        urls_out = [url_out for url, url_out in transformations]
        expected = [
            AfterPreprocessing(utils.api_url, Equals(url_out))
            for url_out in urls_out
            ]
        self.assertThat(urls, MatchesListwise(expected))
