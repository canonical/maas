# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for API annotations."""

__all__ = []

from maasserver.api.annotations import APIDocstringParser
from maasserver.testing.api import APITestCase


class TestAPIAnnotations(APITestCase.ForUser):
    """Tests for API docstring annotations parsing."""

    # Allowed tags
    allowed_tags = APIDocstringParser.allowed_tags
    # Allowed types
    allowed_types = APIDocstringParser.allowed_types

    # Use this sample and modify it in various ways
    # inline to perform tests. Note that all allowed
    # types/tags are (and should be) represented here, and
    # there are tests below that check this.
    sample_api_annotated_docstring = """@description-title Docstring title
    @description Longer description with
    multiple lines.

    @param (string) "param_name" [required=true] param description
    @param-example "param_name" param-ex

    @param (int) "param_name2" [required=false] param2 description
    @param-example "param_name2" param2-ex

    @param (url-string) "param_name3" [required=false] param3 description
    @param-example "param_name3" param3-ex

    @success (content) "success_name" success description
    @success-example "success_name" success content

    @error (http-status-code) "error_name" error description
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

    def test_all_allowed_tags_are_represented_in_test(self):
        """Tests that we have all the allowed tags in our sample docstring."""
        ds_orig = self.sample_api_annotated_docstring

        for t in self.allowed_tags:
            self.assertTrue(ds_orig.find("@%s" % t) != -1)

    def test_all_allowed_types_are_represented_in_test(self):
        """Tests that we have all the allowed types in our sample docstring."""
        ds_orig = self.sample_api_annotated_docstring

        for t in self.allowed_types:
            self.assertTrue(ds_orig.find("(%s)" % t) != -1)

    def test_parse_annotations(self):
        """Tests whether we can parse the sample."""

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
            "Longer description with multiple lines.")

        p = params[0]
        self.assertEqual(p['type'], "String")
        self.assertEqual(p['name'], "param_name")
        self.assertEqual(
            " ".join(p['description'].split()), "param description")
        self.assertEqual(" ".join(p['example'].split()), "param-ex")

        p = params[1]
        self.assertEqual(p['type'], "Int")
        self.assertEqual(p['name'], "param_name2")
        self.assertEqual(
            " ".join(p['description'].split()), "param2 description")
        self.assertEqual(" ".join(p['example'].split()), "param2-ex")

        p = params[2]
        self.assertEqual(p['type'], "URL String")
        self.assertEqual(p['name'], "param_name3")
        self.assertEqual(
            " ".join(p['description'].split()), "param3 description")
        self.assertEqual(" ".join(p['example'].split()), "param3-ex")

        s = successes[0]
        self.assertEqual(s['type'], "Content")
        self.assertEqual(s['name'], "success_name")
        self.assertEqual(
            " ".join(s['description'].split()), "success description")
        self.assertEqual(" ".join(s['example'].split()), "success content")

        e = errors[0]
        self.assertEqual(e['type'], "HTTP Status Code")
        self.assertEqual(e['name'], "error_name")
        self.assertEqual(
            " ".join(e['description'].split()), "error description")
        self.assertEqual(" ".join(e['example'].split()), "error content")

    def test_annotations_present(self):
        """Tests to ensure annotations-present is functioning."""
        docstring_no_annotations = self.sample_api_docstring
        self.assertFalse(APIDocstringParser.is_annotated_docstring(
            docstring_no_annotations))
        docstring_annotations = self.sample_api_annotated_docstring
        self.assertTrue(APIDocstringParser.is_annotated_docstring(
            docstring_annotations))

    def test_annotations_bad_tag(self):
        """Replace a good tag with a bad one and get a syntax error."""
        docstring = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(docstring.replace("@param", "@bad"))
        d = api_docstring_parser.get_dict()
        self.assert_has_syntax_error(d)

    def test_annotations_orphaned_example_tags(self):
        """Tests to ensure orphaned examples are found.

        Orphaned examples are example tags that have no matching
        non-example tag: E.g. param/param-example. The name field
        is used to determine matches.
        """
        docstring = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()
        docstring = docstring.replace(
            "@param-example \"param_name\"",
            "@param-example \"param_name_bad\"")
        api_docstring_parser.parse(docstring)
        d = api_docstring_parser.get_dict()
        self.assert_has_api_warning(d)

        docstring = docstring.replace(
            "@error-example \"error_name\"",
            "@error-example \"error_name_bad\"")
        api_docstring_parser.parse(docstring)
        d = api_docstring_parser.get_dict()
        self.assert_has_api_warning(d)

        docstring = docstring.replace(
            "@success-example \"success_name\"",
            "@success-example \"success_name_bad\"")
        api_docstring_parser.parse(docstring)
        d = api_docstring_parser.get_dict()
        self.assert_has_api_warning(d)

    def test_parse_annotations_indent(self):
        """Indentation should be kept when present."""
        docstring = self.sample_api_annotated_docstring
        ref_string = (
            "Longer description with\n"
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
        """Single quotes should be allowed in annotations."""
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        ds_single_quotes = ds_orig.replace('"', '\'')
        self.assert_has_no_api_warning(
            self.do_parse(api_docstring_parser, ds_single_quotes))

    def test_missing_param_annotation_pieces(self):
        """Tests that missing annotation pieces raises warning.

        Starts with a known good docstring and modifies it inline
        to remove various parts, which should raise warnings.
        """
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # @param (string) "param_name" [required=true] param description

        # All of these should issue warnings
        ds_missing_type = ds_orig.replace('@param (string)', '@param')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_type))

        ds_missing_name = ds_orig.replace(
            '@param (string) "param_name"', '@param (string)')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name))

        ds_missing_required = ds_orig.replace(
            '@param (string) "param_name" [required=true]',
            '@param (string) "param_name"')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_required))

        ds_missing_desc = ds_orig.replace(
            '@param (string) "param_name" [required=true] param description',
            '@param (string) "param_name" [required=true]')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc))

        ds_empty_name = ds_orig.replace(
            '@param (string) "param_name"',
            '@param (string) ""')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name))

    def test_param_required_type_has_correct_value(self):
        """'required' option should only allow true and false.

        Take a known good docstring and replace the 'required'
        option values inline to make sure only true and false
        are accepted (regardless of capitalization).
        """
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        ds_req = ds_orig.replace("required=true", "required=false")
        self.assert_has_no_api_warning(
            self.do_parse(api_docstring_parser, ds_req))

        ds_req = ds_orig.replace("required=true", "required=True")
        self.assert_has_no_api_warning(
            self.do_parse(api_docstring_parser, ds_req))

        ds_req = ds_orig.replace("required=true", "required=False")
        self.assert_has_no_api_warning(
            self.do_parse(api_docstring_parser, ds_req))

        ds_req = ds_orig.replace("required=true", "required=yes")
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_req))

    def test_valid_types(self):
        """Ensure that non-valid types raise warnings."""
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        ds_bad_type = ds_orig.replace("(int)", "(badtype)")

        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_bad_type))

    def test_missing_param_example_annotation_pieces(self):
        """Test for missing pieces of param-example tag.

        Take a known good docstring and remove pieces inline
        to make sure a warning is raised.
        """
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
        """Test for missing pieces of success tag.

        Take a known good docstring and remove pieces inline
        to make sure a warning is raised.
        """
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # All of these should issue warnings
        # @success (content) "success_name" success description
        ds_missing_type = ds_orig.replace('@success (content)', '@success')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_type))

        ds_missing_name = ds_orig.replace(
            '@success (content) "success_name"', '@success (content)')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name))

        ds_missing_desc = ds_orig.replace(
            '@success (content) "success_name" success description',
            '@success (content) "success_name"')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc))

        ds_empty_name = ds_orig.replace(
            '@success (content) "success_name"',
            '@success (content) ""')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name))

    def test_missing_success_example_annotation_pieces(self):
        """Test for missing pieces of success-example tag.

        Take a known good docstring and remove pieces inline
        to make sure a warning is raised.
        """
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
        """Test for missing pieces of error tag.

        Take a known good docstring and remove pieces inline
        to make sure a warning is raised.
        """
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # All of these should issue warnings
        # @error (http-status-code) "error_name" error description
        ds_missing_type = ds_orig.replace(
            '@error (http-status-code)', '@error')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_type))

        ds_missing_name = ds_orig.replace(
            '@error (http-status-code) "error_name"',
            '@error (http-status-code)')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name))

        ds_missing_desc = ds_orig.replace(
            '@error (http-status-code) "error_name" error description',
            '@error (http-status-code) "error_name"')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc))

        ds_empty_name = ds_orig.replace(
            '@error (http-status-code) "error_name"',
            '@error (http-status-code) ""')
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name))

    def test_missing_error_example_annotation_pieces(self):
        """Test for missing pieces of error-example tag.

        Take a known good docstring and remove pieces inline
        to make sure a warning is raised.
        """
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

    def test_empty_description1(self):
        """Test for empty description field in description-title tag."""
        ds_md = self.sample_api_annotated_docstring.replace(
            "Docstring title", "")
        api_docstring_parser = APIDocstringParser()

        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_md))

    def test_empty_description2(self):
        """Test for empty description field in description tag."""
        ds_md = self.sample_api_annotated_docstring.replace(
            "Longer description with\n    multiple lines.", "")
        api_docstring_parser = APIDocstringParser()

        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_md))
