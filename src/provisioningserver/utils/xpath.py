# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""XPath-related utilities."""

import logging

from lxml import etree


def is_compiled_xpath(xpath):
    """Is `xpath` a compiled expression?"""
    return isinstance(xpath, etree.XPath)


def is_compiled_doc(doc):
    """Is `doc` a compiled XPath document evaluator?"""
    return isinstance(doc, etree.XPathDocumentEvaluator)


def match_xpath(xpath, doc):
    """Return a match of expression `xpath` against document `doc`.

    :type xpath: Either `unicode` or `etree.XPath`
    :type doc: Either `etree._ElementTree` or `etree.XPathDocumentEvaluator`

    :rtype: bool
    """
    is_xpath_compiled = is_compiled_xpath(xpath)
    is_doc_compiled = is_compiled_doc(doc)

    if is_xpath_compiled and is_doc_compiled:
        return doc(xpath.path)
    elif is_xpath_compiled:
        return xpath(doc)
    elif is_doc_compiled:
        return doc(xpath)
    else:
        return doc.xpath(xpath)


def try_match_xpath(xpath, doc, logger=logging):
    """See if the XPath expression matches the given XML document.

    Invalid XPath expressions are logged, and are returned as a
    non-match.

    :type xpath: Either `unicode` or `etree.XPath`
    :type doc: Either `etree._ElementTree` or `etree.XPathDocumentEvaluator`

    :rtype: bool
    """
    try:
        # Evaluating an XPath expression against a document with LXML
        # can return a list or a string, and perhaps other types.
        # Casting the return value into a boolean context appears to
        # be the most reliable way of detecting a match.
        return bool(match_xpath(xpath, doc))
    except etree.XPathEvalError as error:
        # Get a plaintext version of `xpath`.
        expr = xpath.path if is_compiled_xpath(xpath) else xpath
        logger.warning("Invalid expression '%s': %s", expr, str(error))
        return False
