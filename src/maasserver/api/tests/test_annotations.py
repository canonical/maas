# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for API annotations."""

__all__ = []

from maasserver.api.annotations import APIDocstringParser
from maasserver.testing.api import APITestCase


class TestAPIAnnotations(APITestCase.ForUser):
    """Tests for API docstring annotations parsing."""

    sample_api_annotated_docstring = """@description-title Docstring title
    @description This is a longer description with
    multiple lines.

    @param (ptype) "param_name" param description
    @param-example "param_name" param-ex

    @success (stype) "success_name" success description
    @success-example "success_name" success content

    @error (etype) "error_name" error description
    @error-example "error_name" error content
    """

    bad_tag_api_docstring = """@description-title Docstring title
    @description This is a longer description with
    multiple lines.

    @param-foo (ptype) "param_name" param description
    @param-example "param_name" param-ex

    @success (stype) "success_name" success description
    @success-example "success_name" success content

    @error (etype) "error_name" error description
    @error-example "error_name" error content
    """

    mismatched_example_api_docstring = """@description-title Docstring title
    @description This is a longer description with
    multiple lines.

    @param (ptype) "param_name" param description
    @param-example "param_name_foo" param-ex

    @success (stype) "success_name" success description
    @success-example "success_name" success content

    @error (etype) "error_name" error description
    @error-example "error_name" error content
    """

    missing_description1_api_docstring = """@description-title
    @description This is a longer description with
    multiple lines.

    @param (ptype) "param_name" param description
    @param-example "param_name_foo" param-ex

    @success (stype) "success_name" success description
    @success-example "success_name" success content

    @error (etype) "error_name" error description
    @error-example "error_name" error content
    """

    missing_description2_api_docstring = """@description-title Docstring title
    @description
    @param (ptype) "param_name" param description
    @param-example "param_name_foo" param-ex

    @success (stype) "success_name" success description
    @success-example "success_name" success content

    @error (etype) "error_name" error description
    @error-example "error_name" error content
    """

    sample_api_docstring = """Docstring title

    This is the other style of docstring found in the
    API code.

    :param name1: param description 1
    :type name1: ptype1

    Returns 404 if not found
    Returns 204 if successful
    """

    def assert_has_api_warning(self, pdict):
        self.assertTrue(pdict['warnings'].find("API_WARNING") != -1)

    def assert_has_no_api_warning(self, pdict):
        self.assertTrue(pdict['warnings'].find("API_WARNING") == -1)

    def assert_has_syntax_error(self, pdict):
        self.assertTrue(pdict['warnings'].find("API_SYNTAX_ERROR") != -1)

    def do_parse(self, api_docstring_parser, docstring):
        api_docstring_parser.parse(docstring)
        return api_docstring_parser.get_dict()

    def test_parse_annotations(self):
        docstring = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(docstring, "method", "uri", "operation")
        d = api_docstring_parser.get_dict()

        params = d['params']
        successes = d['successes']
        errors = d['errors']

        self.assertEqual(d['http_method'], "method")
        self.assertEqual(d['uri'], "uri")
        self.assertEqual(d['operation'], "operation")
        self.assertEqual(d['description_title'], "Docstring title")
        self.assertEqual(
            " ".join(d['description'].split()),
            "This is a longer description with multiple lines.")

        p = params[0]
        self.assertEqual(p['type'], "ptype")
        self.assertEqual(p['name'], "param_name")
        self.assertEqual(
            " ".join(p['description'].split()), "param description")
        self.assertEqual(" ".join(p['example'].split()), "param-ex")

        s = successes[0]
        self.assertEqual(s['type'], "stype")
        self.assertEqual(s['name'], "success_name")
        self.assertEqual(
            " ".join(s['description'].split()), "success description")
        self.assertEqual(" ".join(s['example'].split()), "success content")

        e = errors[0]
        self.assertEqual(e['type'], "etype")
        self.assertEqual(e['name'], "error_name")
        self.assertEqual(
            " ".join(e['description'].split()), "error description")
        self.assertEqual(" ".join(e['example'].split()), "error content")

    def test_annotations_present(self):
        docstring_no_annotations = self.sample_api_docstring
        self.assertFalse(APIDocstringParser.is_annotated_docstring(
            docstring_no_annotations))
        docstring_annotations = self.sample_api_annotated_docstring
        self.assertTrue(APIDocstringParser.is_annotated_docstring(
            docstring_annotations))

    def test_annotations_bad_tag(self):
        docstring = self.bad_tag_api_docstring
        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(docstring)
        d = api_docstring_parser.get_dict()
        self.assert_has_syntax_error(d)

    def test_annotations_mismatched_example(self):
        docstring = self.mismatched_example_api_docstring
        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(docstring)
        d = api_docstring_parser.get_dict()
        self.assert_has_api_warning(d)

    def test_parse_annotations_indent(self):
        docstring = self.sample_api_annotated_docstring
        ref_string = (
            "This is a longer description with\n"
            "    multiple lines.\n\n    "
        )
        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(docstring)
        d = api_docstring_parser.get_dict()

        # Note that we only test one description here because the
        # same code is used to gather all description areas of the
        # tags. E.g. @tag (type) "name" [options] description
        self.assertEqual(d['description'], ref_string)

    def test_whether_name_in_single_quotes_works(self):
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # No warnings here
        ds_single_quotes = ds_orig.replace('"', '\'')
        self.assert_has_no_api_warning(
            self.do_parse(api_docstring_parser, ds_single_quotes))

    def test_missing_param_annotation_pieces(self):
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # All of these should issue warnings
        # @param (ptype) "param_name" param description
        ds_missing_type = ds_orig.replace('@param (ptype)', '@param')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_type))

        ds_missing_name = ds_orig.replace(
            '@param (ptype) "param_name"', '@param (ptype)')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name))

        ds_missing_desc = ds_orig.replace(
            '@param (ptype) "param_name" param description',
            '@param (ptype) "param_name"')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc))

        ds_empty_name = ds_orig.replace(
            '@param (ptype) "param_name"',
            '@param (ptype) ""')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name))

    def test_missing_param_example_annotation_pieces(self):
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # All of these should issue warnings
        # @param-example "param_name" param-ex
        ds_missing_name = ds_orig.replace(
            '@param-example "param_name"', '@param-example')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name))

        ds_missing_desc = ds_orig.replace(
            '@param-example "param_name" param-ex',
            '@param-example "param_name"')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc))

        ds_empty_name = ds_orig.replace(
            '@param-example "param_name"',
            '@param-example ""')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name))

    def test_missing_success_annotation_pieces(self):
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # All of these should issue warnings
        # @success (stype) "success_name" success description
        ds_missing_type = ds_orig.replace('@success (stype)', '@success')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_type))

        ds_missing_name = ds_orig.replace(
            '@success (stype) "success_name"', '@success (stype)')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name))

        ds_missing_desc = ds_orig.replace(
            '@success (stype) "success_name" success description',
            '@success (stype) "success_name"')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc))

        ds_empty_name = ds_orig.replace(
            '@success (stype) "success_name"',
            '@success (stype) ""')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name))

    def test_missing_success_example_annotation_pieces(self):
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # All of these should issue warnings
        # @success-example "success_name" success-ex

        ds_missing_name = ds_orig.replace(
            '@success-example "success_name"', '@success-example')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name))

        ds_missing_desc = ds_orig.replace(
            '@success-example "success_name" success content',
            '@success-example "success_name"')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc))

        ds_empty_name = ds_orig.replace(
            '@success-example "success_name"',
            '@success-example ""')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name))

    def test_missing_error_annotation_pieces(self):
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # All of these should issue warnings
        # @error (etype) "error_name" error description
        ds_missing_type = ds_orig.replace('@error (etype)', '@error')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_type))

        ds_missing_name = ds_orig.replace(
            '@error (etype) "error_name"', '@error (etype)')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name))

        ds_missing_desc = ds_orig.replace(
            '@error (etype) "error_name" error description',
            '@error (etype) "error_name"')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc))

        ds_empty_name = ds_orig.replace(
            '@error (etype) "error_name"',
            '@error (etype) ""')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name))

    def test_missing_error_example_annotation_pieces(self):
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # All of these should issue warnings
        # @error-example "error_name" error content

        ds_missing_name = ds_orig.replace(
            '@error-example "error_name"', '@error-example')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name))

        ds_missing_desc = ds_orig.replace(
            '@error-example "error_name" error content',
            '@error-example "error_name"')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc))

        ds_empty_name = ds_orig.replace(
            '@error-example "error_name"',
            '@error-example ""')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name))

    def test_missing_description1(self):
        ds_md1 = self.missing_description1_api_docstring
        api_docstring_parser = APIDocstringParser()

        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_md1))

    def test_missing_description2(self):
        ds_md2 = self.missing_description1_api_docstring
        api_docstring_parser = APIDocstringParser()

        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_md2))
