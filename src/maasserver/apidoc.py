# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities to help document/describe the public facing API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "describe_handler",
    "find_api_handlers",
    "generate_api_docs",
    ]

from inspect import getdoc
from itertools import izip_longest
from urllib import quote
from urlparse import urljoin

from django.conf import settings
from piston.doc import generate_doc
from piston.handler import HandlerMetaClass


def find_api_handlers(module):
    """Find the API handlers defined in `module`.

    Handlers are of type :class:`HandlerMetaClass`.

    :rtype: Generator, yielding handlers.
    """
    try:
        names = module.__all__
    except AttributeError:
        names = sorted(
            name for name in dir(module)
            if not name.startswith("_"))
    for name in names:
        candidate = getattr(module, name)
        if isinstance(candidate, HandlerMetaClass):
            yield candidate


def generate_api_docs(handlers):
    """Generate ReST documentation objects for the ReST API.

    Yields Piston Documentation objects describing the current registered
    handlers.

    This also ensures that handlers define 'resource_uri' methods. This is
    easily forgotten and essential in order to generate proper documentation.

    :return: Generates :class:`piston.doc.HandlerDocumentation` instances.
    """
    sentinel = object()
    for handler in handlers:
        if getattr(handler, "resource_uri", sentinel) is sentinel:
            raise AssertionError(
                "Missing resource_uri in %s" % handler.__name__)
        yield generate_doc(handler)


def merge(*iterables):
    """Merge iterables.

    The iterables are iterated in lock-step. For the values at each iteration,
    the first defined one is yielded, the rest are discarded.

    This is useful for unpacking variable length results with defaults:

      >>> a, b, c = merge("AB", "123")
      >>> print(a, b, c)
      A B 3

    """
    undefined = object()
    for values in izip_longest(*iterables, fillvalue=undefined):
        yield next(value for value in values if value is not undefined)


def describe_handler(handler):
    """Return a serialisable description of a handler.

    :type handler: :class:`BaseHandler` instance that has been decorated by
        `api_operations`.
    """
    # Avoid circular imports.
    from maasserver.api import dispatch_methods

    uri_template = generate_doc(handler).resource_uri_template
    if uri_template is None:
        uri_template = settings.DEFAULT_MAAS_URL
    else:
        uri_template = urljoin(settings.DEFAULT_MAAS_URL, uri_template)

    view_name, uri_params, uri_kw = merge(
        handler.resource_uri(), (None, (), {}))
    assert uri_kw == {}, (
        "Resource URI specifications with keyword parameters are not yet "
        "supported: handler=%r; view_name=%r" % (handler, view_name))

    actions = []
    operation_methods = getattr(handler, "_available_api_methods", {})
    for http_method in handler.allowed_methods:
        if http_method in operation_methods:
            # Default Piston CRUD method has been overridden; inspect
            # custom operations instead.
            operations = handler._available_api_methods[http_method]
            for op, func in operations.items():
                desc = {
                    "doc": getdoc(func),
                    "method": http_method,
                    "op": op,
                    "uri": "%s?op=%s" % (uri_template, quote(op)),
                    "uri_params": uri_params,
                    }
                actions.append(desc)
        else:
            # Default Piston CRUD method still stands.
            op = dispatch_methods[http_method]
            func = getattr(handler, op)
            desc = {
                "doc": getdoc(func),
                "method": http_method,
                "uri": uri_template,
                "uri_params": uri_params,
                }
            actions.append(desc)

    return {
        "name": handler.__name__,
        "doc": getdoc(handler),
        "actions": actions,
        }
