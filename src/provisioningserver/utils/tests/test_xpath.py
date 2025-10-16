# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for XPath utilities."""

from textwrap import dedent

from lxml import etree
from testscenarios import multiply_scenarios

from maastesting.testcase import MAASTestCase
from provisioningserver.utils import xpath as xpath_module
from provisioningserver.utils.xpath import try_match_xpath


class TestTryMatchXPathScenarios(MAASTestCase):
    def scenario(name, xpath, doc, expected_result, expected_log=""):
        """Return a scenario (for `testscenarios`) to test `try_match_xpath`.

        This is a convenience function to reduce the amount of
        boilerplate when constructing `scenarios_inputs` later on.

        The scenario it constructs defines an XML document, and XPath
        expression, the expectation as to whether it will match or
        not, and the expected log output.
        """
        doc = etree.fromstring(doc).getroottree()
        return (
            name,
            dict(
                xpath=xpath,
                doc=doc,
                expected_result=expected_result,
                expected_log=dedent(expected_log),
            ),
        )

    # Exercise try_match_xpath with a variety of different inputs.
    scenarios_inputs = (
        scenario("expression matches", "/foo", "<foo/>", True),
        scenario("expression does not match", "/foo", "<bar/>", False),
        scenario(
            "text expression matches", "/foo/text()", "<foo>bar</foo>", True
        ),
        scenario(
            "text expression does not match",
            "/foo/text()",
            "<foo></foo>",
            False,
        ),
        scenario(
            "string expression matches", "string()", "<foo>bar</foo>", True
        ),
        scenario(
            "string expression does not match",
            "string()",
            "<foo></foo>",
            False,
        ),
        scenario(
            "unrecognised namespace",
            "/foo:bar",
            "<foo/>",
            False,
            expected_log="Invalid expression '/foo:bar': Undefined namespace prefix",
        ),
    )

    # Exercise try_match_xpath with and without compiled XPath
    # expressions.
    scenarios_xpath_compiler = (
        ("xpath-compiler=XPath", dict(xpath_compile=etree.XPath)),
        ("xpath-compiler=None", dict(xpath_compile=lambda expr: expr)),
    )

    # Exercise try_match_xpath with and without documents wrapped in
    # an XPathDocumentEvaluator.
    scenarios_doc_compiler = (
        (
            "doc-compiler=XPathDocumentEvaluator",
            dict(doc_compile=etree.XPathDocumentEvaluator),
        ),
        ("doc-compiler=None", dict(doc_compile=lambda doc: doc)),
    )

    scenarios = multiply_scenarios(
        scenarios_inputs, scenarios_xpath_compiler, scenarios_doc_compiler
    )

    def setUp(self):
        super().setUp()
        self.logger = self.patch(xpath_module, "logger")

    def test(self):
        xpath = self.xpath_compile(self.xpath)
        doc = self.doc_compile(self.doc)
        self.assertIs(self.expected_result, try_match_xpath(xpath, doc))
        if self.expected_log:
            self.logger.warn.assert_called_once()
            args, _ = self.logger.warn.call_args
            self.assertEqual(self.expected_log, args[0])


class TestTryMatchXPath(MAASTestCase):
    def test_logs_to_specified_logger(self):
        logger = self.patch(xpath_module, "logger")
        xpath = etree.XPath("/foo:bar")
        doc = etree.XML("<foo/>")
        try_match_xpath(xpath, doc)
        logger.warn.assert_called_once_with(
            "Invalid expression '/foo:bar': Undefined namespace prefix"
        )
