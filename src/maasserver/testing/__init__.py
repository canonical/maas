# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver`."""

__all__ = [
    "extract_redirect",
    "get_content_links",
    "get_data",
    "get_prefixed_form_data",
    "NoReceivers",
]

from collections.abc import Iterable
from contextlib import contextmanager
import http.client
from itertools import chain
import os
from urllib.parse import urlparse

from lxml.html import fromstring


def extract_redirect(http_response):
    """Extract redirect target from an http response object.

    Only the http path part of the redirect is ignored; protocol and host
    name, if present, are not included in the result.

    If the response is not a redirect, this raises :class:`ValueError` with
    a descriptive error message.

    :param http_response: A response returned from an http request.
    :type http_response: :class:`HttpResponse`
    :return: The "path" part of the target that `http_response` redirects to.
    :raises: ValueError
    """
    if http_response.status_code != http.client.FOUND:
        raise ValueError(
            "Not a redirect: http status %d. Content: %s"
            % (http_response.status_code, http_response.content[:80])
        )
    target_url = http_response["Location"]
    parsed_url = urlparse(target_url)
    return parsed_url.path


def get_data(filename):
    """Read the content of a file in `src/maasserver/tests`.

    Some tests use this to read fixed data stored in files in
    `src/maasserver/tests/data/`.

    Where possible, provide data in-line in tests, or use fakes, to keep the
    information close to the tests that rely on it.

    :param filename: A file path relative to `src/maasserver/tests` in
        this branch.
    :return: the content of the file as `str`.
    """
    return _get_data(filename, "r")


def get_binary_data(filename):
    """Read the content of a file in `src/maasserver/tests`.

    Some tests use this to read fixed data stored in files in
    `src/maasserver/tests/data/`.

    Where possible, provide data in-line in tests, or use fakes, to keep the
    information close to the tests that rely on it.

    :param filename: A file path relative to `src/maasserver/tests` in
        this branch.
    :return: Binary contents of the file, as `bytes`.
    """
    return _get_data(filename, "rb")


def _get_data(filename: str, mode: str = "r"):
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "tests", filename
    )
    with open(path, mode) as fd:
        return fd.read()


def get_prefixed_form_data(prefix, data):
    """Prefix entries in a dict of form parameters with a form prefix.

    Also, add a parameter "<prefix>_submit" to indicate that the form with
    the given prefix is being submitted.

    Use this to construct a form submission if the form uses a prefix (as it
    would if there are multiple forms on the page).

    :param prefix: Form prefix string.
    :param data: A dict of form parameters.
    :return: A new dict of prefixed form parameters.
    """
    result = {f"{prefix}-{key}": value for key, value in data.items()}
    result.update({"%s_submit" % prefix: 1})
    return result


def get_content_links(response, element="#content"):
    """Extract links from :class:`HttpResponse` content.

    :param response: An HTTP response object.  Only its `content` attribute is
        used.
    :param element: Optional CSS selector for the node(s) in the content whose
        links should be extracted.  Only links inside the part of the content
        that matches this selector will be extracted; any other links will be
        ignored.  Defaults to `#content`, which is the main document.
    :return: List of link targets found in any matching parts of the document,
        including their nested tags.  If a link is in a DOM subtree that
        matches `element` at multiple levels, it may be counted more than once.
        Otherwise, links are returned in the same order in which they are found
        in the document.
    """
    doc = fromstring(response.content)
    links_per_matching_node = chain.from_iterable(
        [elem.get("href") for elem in matching_node.cssselect("a")]
        for matching_node in doc.cssselect(element)
    )
    return list(links_per_matching_node)


@contextmanager
def NoReceivers(signals):
    """Disconnect signal receivers from the supplied signals.

    :param signals: A signal (or iterable of signals) for which to disable
        signal receivers while in the context manager.
    :type signal: django.dispatch.Signal
    """
    saved = dict()
    if not isinstance(signals, Iterable):
        signals = [signals]
    for signal in signals:
        saved[signal] = signal.receivers
        signal.receivers = []
    try:
        yield
    finally:
        for signal in signals:
            signal.receivers = saved[signal]
