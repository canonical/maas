# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for API annotations."""

import os

from maasserver.api.annotations import APIDocstringParser
from maasserver.api.templates import APITemplateRenderer
from maasserver.testing.api import APITestCase


class TestAPIAnnotations(APITestCase.ForUser):
    """Tests for API docstring annotations parsing."""

    # Allowed tags
    allowed_tags = APIDocstringParser.allowed_tags
    # Allowed types
    allowed_types = APIDocstringParser.allowed_types

    # URI templates for testing the examples database. The parser uses the
    # URI template to name an examples database. So, here, the parser would
    # look for "examples/for-tests.json". We have plural and singular beause
    # the API often references both plural and singular operations. E.g.
    # zone and zones. Both should use the same examples database.
    #
    # Also, we need to pass this to every parse method call so that we don't
    # see spurious API warnings when the parse cannot find an examples database
    # that the sample_api_annotated_docstring is referencing.
    test_uri_singular = "/MAAS/api/2.0/for-test/{foobar}/"
    test_uri_plural = "/MAAS/api/2.0/for-tests/{foobar}/"

    # This is the name of the template file used to render API
    api_tempita_template = "tmpl-apidoc.rst"

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

    @param (url-string) "param_name3" [required=true] param3 description
    @param-example "param_name3" param3-ex

    @param (json) "param_name4" [required=false] param4 description
    @param-example "param_name4"
        {
            "id": 1,
            "foo": "bar"
        }

    @param (boolean) "param_name5" [required=false] param5 description
    @param-example "param_name5" True

    @param (float) "param_name6" [required=false] param6 description
    @param-example "param_name6" 1.5

    @param (string) "param_name7" [required=false,formatting=true] formatting

    @success (content) "success_name" success description
    @success-example "success_name" success content

    @success (content) "success_with_exdb" success description
    @success-example "success_with_exdb" [exkey=key1] placeholder text

    @success (content) "success_inherit_node" success description
    @success-example "success_inherit_node" [exkey=read-node] placeholder text

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
        self.assertNotEqual(pdict["warnings"].find("API_WARNING"), -1)

    def assert_has_no_api_warning(self, pdict):
        self.assertEqual(pdict["warnings"].find("API_WARNING"), -1)

    def assert_has_syntax_error(self, pdict):
        self.assertNotEqual(pdict["warnings"].find("API_SYNTAX_ERROR"), -1)

    def do_parse(self, api_docstring_parser, docstring):
        api_docstring_parser.parse(docstring, uri=self.test_uri_singular)
        return api_docstring_parser.get_dict()

    def test_all_allowed_tags_are_represented_in_test(self):
        """Tests that we have all the allowed tags in our sample docstring."""
        ds_orig = self.sample_api_annotated_docstring

        for t in self.allowed_tags:
            self.assertNotEqual(ds_orig.find("@%s" % t), -1)

    def test_all_allowed_types_are_represented_in_test(self):
        """Tests that we have all the allowed types in our sample docstring."""
        ds_orig = self.sample_api_annotated_docstring

        for t in self.allowed_types:
            self.assertNotEqual(ds_orig.find("(%s)" % t), -1)

    def test_parse_annotations(self):
        """Tests whether we can parse the sample."""

        docstring = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(
            docstring,
            http_method="mymethod",
            uri=self.test_uri_singular,
            operation="myoperation",
        )
        d = api_docstring_parser.get_dict()

        params = d["params"]
        successes = d["successes"]
        errors = d["errors"]

        self.assertEqual(d["http_method"], "mymethod")
        self.assertEqual(d["uri"], self.test_uri_singular)
        self.assertEqual(d["operation"], "myoperation")
        self.assertEqual(d["description_title"], "Docstring title")
        self.assertEqual(
            " ".join(d["description"].split()),
            "Longer description with multiple lines.",
        )

        p = params[0]
        self.assertEqual(p["type"], "String")
        self.assertEqual(p["name"], "param_name")
        self.assertEqual(
            " ".join(p["description"].split()), "param description"
        )
        self.assertEqual(" ".join(p["example"].split()), "param-ex")

        p = params[1]
        self.assertEqual(p["type"], "Int")
        self.assertEqual(p["name"], "param_name2")
        self.assertEqual(
            " ".join(p["description"].split()), "param2 description"
        )
        self.assertEqual(" ".join(p["example"].split()), "param2-ex")

        p = params[2]
        self.assertEqual(p["type"], "URL String")
        self.assertEqual(p["name"], "param_name3")
        self.assertEqual(
            " ".join(p["description"].split()), "param3 description"
        )
        self.assertEqual(" ".join(p["example"].split()), "param3-ex")

        p = params[3]
        self.assertEqual(p["type"], "JSON")
        self.assertEqual(p["name"], "param_name4")
        self.assertEqual(
            " ".join(p["description"].split()), "param4 description"
        )
        self.assertEqual(
            " ".join(p["example"].split()), '{ "id": 1, "foo": "bar" }'
        )

        p = params[4]
        self.assertEqual(p["type"], "Boolean")
        self.assertEqual(p["name"], "param_name5")
        self.assertEqual(
            " ".join(p["description"].split()), "param5 description"
        )
        self.assertEqual(" ".join(p["example"].split()), "True")

        p = params[5]
        self.assertEqual(p["type"], "Float")
        self.assertEqual(p["name"], "param_name6")
        self.assertEqual(
            " ".join(p["description"].split()), "param6 description"
        )
        self.assertEqual(" ".join(p["example"].split()), "1.5")

        s = successes[0]
        self.assertEqual(s["type"], "Content")
        self.assertEqual(s["name"], "success_name")
        self.assertEqual(
            " ".join(s["description"].split()), "success description"
        )
        self.assertEqual(" ".join(s["example"].split()), "success content")

        e = errors[0]
        self.assertEqual(e["type"], "HTTP Status Code")
        self.assertEqual(e["name"], "error_name")
        self.assertEqual(
            " ".join(e["description"].split()), "error description"
        )
        self.assertEqual(" ".join(e["example"].split()), "error content")

    def test_annotations_present(self):
        """Tests to ensure annotations-present is functioning."""
        docstring_no_annotations = self.sample_api_docstring
        self.assertFalse(
            APIDocstringParser.is_annotated_docstring(docstring_no_annotations)
        )
        docstring_annotations = self.sample_api_annotated_docstring
        self.assertTrue(
            APIDocstringParser.is_annotated_docstring(docstring_annotations)
        )

    def test_annotations_bad_tag(self):
        """Replace a good tag with a bad one and get a syntax error."""
        docstring = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(
            docstring.replace("@param", "@bad"), uri=self.test_uri_singular
        )
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
            '@param-example "param_name"', '@param-example "param_name_bad"'
        )
        api_docstring_parser.parse(docstring, uri=self.test_uri_singular)
        d = api_docstring_parser.get_dict()
        self.assert_has_api_warning(d)

        docstring = docstring.replace(
            '@error-example "error_name"', '@error-example "error_name_bad"'
        )
        api_docstring_parser.parse(docstring, uri=self.test_uri_singular)
        d = api_docstring_parser.get_dict()
        self.assert_has_api_warning(d)

        docstring = docstring.replace(
            '@success-example "success_name"',
            '@success-example "success_name_bad"',
        )
        api_docstring_parser.parse(docstring, uri=self.test_uri_singular)
        d = api_docstring_parser.get_dict()
        self.assert_has_api_warning(d)

    def test_parse_annotations_indent_descriptions(self):
        """Indentation should be kept when present in descriptions."""
        docstring = self.sample_api_annotated_docstring
        ref_string = "Longer description with\n    multiple lines.\n\n    "
        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(docstring, uri=self.test_uri_singular)
        d = api_docstring_parser.get_dict()

        # Note that we only test one description here because the
        # same code is used to gather all description areas of the
        # tags. E.g. @tag (type) "name" [options] description
        self.assertEqual(d["description"], ref_string)

    def test_parse_annotations_indent_example(self):
        """Indentation should be kept when present in examples."""
        docstring = self.sample_api_annotated_docstring
        ref_string = (
            "{\n"
            '            "id": 1,\n'
            '            "foo": "bar"\n'
            "        }\n\n    "
        )
        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(docstring, uri=self.test_uri_singular)
        d = api_docstring_parser.get_dict()

        # Note that we only test one example here because the
        # same code is used to gather all description areas of the
        # tags. E.g. @tag-example (type) "name" [options] description
        params = d["params"]
        self.assertEqual(params[3]["example"], ref_string)

    def test_whether_name_in_single_quotes_works(self):
        """Single quotes should be allowed in annotations."""
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        ds_single_quotes = ds_orig.replace('"', "'")
        self.assert_has_no_api_warning(
            self.do_parse(api_docstring_parser, ds_single_quotes)
        )

    def test_missing_param_annotation_pieces(self):
        """Tests that missing annotation pieces raises warning.

        Starts with a known good docstring and modifies it inline
        to remove various parts, which should raise warnings.
        """
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # @param (string) "param_name" [required=true] param description

        # All of these should issue warnings
        ds_missing_type = ds_orig.replace("@param (string)", "@param")
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_type)
        )

        ds_missing_name = ds_orig.replace(
            '@param (string) "param_name"', "@param (string)"
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name)
        )

        ds_missing_required = ds_orig.replace(
            '@param (string) "param_name" [required=true]',
            '@param (string) "param_name"',
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_required)
        )

        ds_missing_desc = ds_orig.replace(
            '@param (string) "param_name" [required=true] param description',
            '@param (string) "param_name" [required=true]',
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc)
        )

        ds_empty_name = ds_orig.replace(
            '@param (string) "param_name"', '@param (string) ""'
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name)
        )

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
            self.do_parse(api_docstring_parser, ds_req)
        )

        ds_req = ds_orig.replace("required=true", "required=True")
        self.assert_has_no_api_warning(
            self.do_parse(api_docstring_parser, ds_req)
        )

        ds_req = ds_orig.replace("required=true", "required=False")
        self.assert_has_no_api_warning(
            self.do_parse(api_docstring_parser, ds_req)
        )

        ds_req = ds_orig.replace("required=true", "required=yes")
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_req)
        )

    def test_param_formatting_type_has_correct_value(self):
        """'formatting' option should only allow true and false.

        Take a known good docstring and replace the 'required'
        option values inline to make sure only true and false
        are accepted (regardless of capitalization).
        """
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        ds_req = ds_orig.replace("formatting=true", "formatting=false")
        self.assert_has_no_api_warning(
            self.do_parse(api_docstring_parser, ds_req)
        )

        ds_req = ds_orig.replace("formatting=true", "formatting=True")
        self.assert_has_no_api_warning(
            self.do_parse(api_docstring_parser, ds_req)
        )

        ds_req = ds_orig.replace("formatting=true", "formatting=False")
        self.assert_has_no_api_warning(
            self.do_parse(api_docstring_parser, ds_req)
        )

        ds_req = ds_orig.replace("formatting=true", "formatting=yes")
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_req)
        )

    def test_valid_types(self):
        """Ensure that non-valid types raise warnings."""
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        ds_bad_type = ds_orig.replace("(int)", "(badtype)")

        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_bad_type)
        )

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
            '@param-example "param_name"', "@param-example"
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name)
        )

        ds_missing_desc = ds_orig.replace(
            '@param-example "param_name" param-ex',
            '@param-example "param_name"',
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc)
        )

        ds_empty_name = ds_orig.replace(
            '@param-example "param_name"', '@param-example ""'
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name)
        )

    def test_missing_success_annotation_pieces(self):
        """Test for missing pieces of success tag.

        Take a known good docstring and remove pieces inline
        to make sure a warning is raised.
        """
        ds_orig = self.sample_api_annotated_docstring
        api_docstring_parser = APIDocstringParser()

        # All of these should issue warnings
        # @success (content) "success_name" success description
        ds_missing_type = ds_orig.replace("@success (content)", "@success")
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_type)
        )

        ds_missing_name = ds_orig.replace(
            '@success (content) "success_name"', "@success (content)"
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name)
        )

        ds_missing_desc = ds_orig.replace(
            '@success (content) "success_name" success description',
            '@success (content) "success_name"',
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc)
        )

        ds_empty_name = ds_orig.replace(
            '@success (content) "success_name"', '@success (content) ""'
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name)
        )

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
            '@success-example "success_name"', "@success-example"
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name)
        )

        ds_missing_desc = ds_orig.replace(
            '@success-example "success_name" success content',
            '@success-example "success_name"',
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc)
        )

        ds_empty_name = ds_orig.replace(
            '@success-example "success_name"', '@success-example ""'
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name)
        )

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
            "@error (http-status-code)", "@error"
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_type)
        )

        ds_missing_name = ds_orig.replace(
            '@error (http-status-code) "error_name"',
            "@error (http-status-code)",
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name)
        )

        ds_missing_desc = ds_orig.replace(
            '@error (http-status-code) "error_name" error description',
            '@error (http-status-code) "error_name"',
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc)
        )

        ds_empty_name = ds_orig.replace(
            '@error (http-status-code) "error_name"',
            '@error (http-status-code) ""',
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name)
        )

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
            '@error-example "error_name"', "@error-example"
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_name)
        )

        ds_missing_desc = ds_orig.replace(
            '@error-example "error_name" error content',
            '@error-example "error_name"',
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_missing_desc)
        )

        ds_empty_name = ds_orig.replace(
            '@error-example "error_name"', '@error-example ""'
        )
        self.assert_has_api_warning(
            self.do_parse(api_docstring_parser, ds_empty_name)
        )

    def test_empty_description1(self):
        """Test for empty description field in description-title tag."""
        ds_md = self.sample_api_annotated_docstring.replace(
            "Docstring title", ""
        )
        api_docstring_parser = APIDocstringParser()

        self.assert_has_api_warning(self.do_parse(api_docstring_parser, ds_md))

    def test_empty_description2(self):
        """Test for empty description field in description tag."""
        ds_md = self.sample_api_annotated_docstring.replace(
            "Longer description with\n    multiple lines.", ""
        )
        api_docstring_parser = APIDocstringParser()

        self.assert_has_api_warning(self.do_parse(api_docstring_parser, ds_md))

    def test_find_examples_db(self):
        """Ensure parser correctly finds example databases."""
        ds = self.sample_api_annotated_docstring

        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(ds, uri=self.test_uri_singular)
        d = api_docstring_parser.get_dict()

        s = d["successes"][1]

        self.assertEqual(" ".join(s["example"].split()), '{ "name": "value" }')

        api_docstring_parser.parse(ds, uri=self.test_uri_plural)
        d = api_docstring_parser.get_dict()

        s = d["successes"][1]

        self.assertEqual(" ".join(s["example"].split()), '{ "name": "value" }')

    def test_warn_on_missing_example_db_entry(self):
        """Ensure we see a warning if there is a missing examples db entry."""
        ds_orig = self.sample_api_annotated_docstring

        ds_bad_exkey = ds_orig.replace(
            '"success_with_exdb" [exkey=key1]',
            '"success_with_exdb" [exkey=badkey]',
        )

        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(ds_bad_exkey, uri=self.test_uri_singular)
        d = api_docstring_parser.get_dict()

        self.assert_has_api_warning(d)

    def test_warn_on_missing_example_db_when_entry_referenced(self):
        """Missing examples db.

        If an examples db does not exist for some given URI (like when it
        simply hasn't been created yet) and a key from that missing DB is
        referenced by the API, we should see a warning.

        Note that _not_ having an examples db for a particular operation is a
        normal and acceptable condition (it takes a while to create one). It
        only becomes an error condition when the API tries to reference
        something inside a non-existent examples database.
        """
        ds = self.sample_api_annotated_docstring

        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(ds, uri="bad_uri")
        d = api_docstring_parser.get_dict()

        self.assert_has_api_warning(d)

    def test_load_nodes_examples_by_default(self):
        """Nodes examples should be loading by default.

        Some API objects like machines and devices inherit operations from
        nodes, so when we load the examples database, we always start with
        nodes and add on object-specific examples.
        """
        ds = self.sample_api_annotated_docstring

        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(ds, uri=self.test_uri_plural)
        d = api_docstring_parser.get_dict()

        # index=2 contains the example with inherited examples from
        # example/nodes.json
        s = d["successes"][2]

        # The presence of the 'resource-uri' string is a good indicator
        # that the 'read-node' key has picked up the JSON object and
        # converted it to a string for output in API docs.
        self.assertNotEqual(s["example"].find("resource_uri"), -1)

    def test_template_renders_with_no_warnings(self):
        """The Tempita tmpl-api.rst template should render for the sample
        annotated API docstring with no errors.
        """
        ds = self.sample_api_annotated_docstring
        template = APITemplateRenderer()
        template_path = "{}/../{}".format(
            os.path.dirname(__file__),
            self.api_tempita_template,
        )

        api_docstring_parser = APIDocstringParser()
        api_docstring_parser.parse(ds, uri=self.test_uri_plural)

        result = template.apply_template(template_path, api_docstring_parser)

        self.assertNotIn("API_WARNING", result)
