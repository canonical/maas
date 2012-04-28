# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

"""Tests for `maasserver`."""

__metaclass__ = type
__all__ = [
    "extract_redirect",
    "get_content_links",
    "get_data",
    "get_fake_provisioning_api_proxy",
    "get_prefixed_form_data",
    "reload_object",
    "reload_objects",
    ]

import httplib
import os
from urlparse import urlparse
from uuid import uuid1

from lxml.html import fromstring
from provisioningserver.testing import fakeapi

# Current (singleton) fake provisioning API server.
fake_provisioning_proxy = None


def get_fake_provisioning_api_proxy():
    """Produce a fake provisioning API proxy.

    The fake server is a singleton, so as to provide a realistically coherent
    fake session.  If you want a clean slate, call
    `reset_fake_provisioning_api_proxy` and the next call here will create a
    fresh instance.
    """
    global fake_provisioning_proxy
    if fake_provisioning_proxy is None:
        fake_provisioning_proxy = fakeapi.FakeSynchronousProvisioningAPI()
        distro = fake_provisioning_proxy.add_distro(
            "distro-%s" % uuid1().get_hex(),
            "initrd", "kernel")
        fake_provisioning_proxy.add_profile(
            "profile-%s" % uuid1().get_hex(),
            distro)
    return fake_provisioning_proxy


def reset_fake_provisioning_api_proxy():
    """Reset the fake provisioning API server.

    The next call to `get_fake_provisioning_api_proxy` will create a fresh
    instance.
    """
    global fake_provisioning_proxy
    fake_provisioning_proxy = None


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

    If the object has been deleted, this will raise the `DoesNotExist`
    exception for its model class.

    :param model_object: Model object to reload.
    :type model_object: Concrete `Model` subtype.
    :return: Freshly-loaded instance of `model_object`.
    :rtype: Same as `model_object`.
    """
    model_class = model_object.__class__
    try:
        return model_class.objects.get(id=model_object.id)
    except model_class.DoesNotExist:
        return None


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
    """Extract links from :class:`HttpResponse` #content element."""
    doc = fromstring(response.content)
    [content_node] = doc.cssselect(element)
    return [elem.get('href') for elem in content_node.cssselect('a')]
