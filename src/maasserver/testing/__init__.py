# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

"""Tests for `maasserver`."""

str = None

__metaclass__ = type
__all__ = [
    "extract_redirect",
    "get_content_links",
    "get_data",
    "get_prefixed_form_data",
    "reload_object",
    "reload_objects",
    ]

import httplib
import os
from urlparse import urlparse

from lxml.html import fromstring
from maasserver.utils.orm import get_one


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
    if http_response.status_code != httplib.FOUND:
        raise ValueError(
            "Not a redirect: http status %d.  Content: %s"
            % (http_response.status_code, http_response.content[:80]))
    target_url = http_response['Location']
    parsed_url = urlparse(target_url)
    return parsed_url.path


def reload_object(model_object):
    """Reload `obj` from the database.

    Use this when a test needs to inspect changes to model objects made by
    the API.

    If the object has been deleted, this will return None.

    :param model_object: Model object to reload.
    :type model_object: Concrete `Model` subtype.
    :return: Freshly-loaded instance of `model_object`, or None.
    :rtype: Same as `model_object`.
    """
    model_class = model_object.__class__
    return get_one(model_class.objects.filter(id=model_object.id))


def reload_objects(model_class, model_objects):
    """Reload `model_objects` of type `model_class` from the database.

    Use this when a test needs to inspect changes to model objects made by
    the API.

    If any of the objects have been deleted, they will not be included in
    the result.

    :param model_class: `Model` class to reload from.
    :type model_class: Class.
    :param model_objects: Objects to reload from the database.
    :type model_objects: Sequence of `model_class` objects.
    :return: Reloaded objects, in no particular order.
    :rtype: Sequence of `model_class` objects.
    """
    assert all(isinstance(obj, model_class) for obj in model_objects)
    return model_class.objects.filter(
        id__in=[obj.id for obj in model_objects])


def get_data(filename):
    """Utility method to read the content of files in
    src/maasserver/tests.

    Usually used to read files in src/maasserver/tests/data."""
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'tests', filename)
    return file(path).read()


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
    result = {'%s-%s' % (prefix, key): value for key, value in data.items()}
    result.update({'%s_submit' % prefix: 1})
    return result


def get_content_links(response, element='#content'):
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
    links_per_matching_node = [
        [elem.get('href') for elem in matching_node.cssselect('a')]
        for matching_node in doc.cssselect(element)
        ]
    return sum(links_per_matching_node, [])
