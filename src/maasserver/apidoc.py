# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities to help document/describe the public facing API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "describe_handler",
    "describe_resource",
    "find_api_resources",
    "generate_api_docs",
    ]

from inspect import getdoc
from itertools import izip_longest

from django.core.urlresolvers import (
    get_resolver,
    RegexURLPattern,
    RegexURLResolver,
    )
from maasserver.api_support import OperationsResource
from piston.authentication import NoAuthentication
from piston.doc import generate_doc
from piston.handler import BaseHandler
from piston.resource import Resource


def accumulate_api_resources(resolver, accumulator):
    """Accumulate handlers from the given resolver.

    Handlers are of type :class:`HandlerMetaClass`, and must define a
    `resource_uri` method.

    :rtype: Generator, yielding handlers.
    """
    p_has_resource_uri = lambda resource: (
        getattr(resource.handler, "resource_uri", None) is not None)
    for pattern in resolver.url_patterns:
        if isinstance(pattern, RegexURLResolver):
            accumulate_api_resources(pattern, accumulator)
        elif isinstance(pattern, RegexURLPattern):
            if isinstance(pattern.callback, Resource):
                resource = pattern.callback
                if p_has_resource_uri(resource):
                    accumulator.add(resource)
        else:
            raise AssertionError(
                "Not a recognised pattern or resolver: %r" % (pattern,))


def find_api_resources(urlconf=None):
    """Find the API resources defined in `urlconf`.

    :rtype: :class:`set` of :class:`Resource` instances.
    """
    resolver, accumulator = get_resolver(urlconf), set()
    accumulate_api_resources(resolver, accumulator)
    return accumulator


def generate_api_docs(resources):
    """Generate ReST documentation objects for the ReST API.

    Yields Piston Documentation objects describing the given resources.

    This also ensures that handlers define 'resource_uri' methods. This is
    easily forgotten and essential in order to generate proper documentation.

    :return: Generates :class:`piston.doc.HandlerDocumentation` instances.
    """
    sentinel = object()
    for resource in resources:
        handler = type(resource.handler)
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


def describe_actions(handler):
    """Describe the actions that `handler` supports.

    For each action, which could be a CRUD operation or a custom (piggybacked)
    operation, a dict with the following entries is generated:

      method: string, HTTP method.
      name: string, a human-friendly name for the action.
      doc: string, documentation about the action.
      op: string or None, the op parameter to pass in requests for
          non-CRUD/ReSTful requests.
      restful: Indicates if this is a CRUD/ReSTful action.

    """
    getname = OperationsResource.crudmap.get
    for signature, function in handler.exports.items():
        http_method, operation = signature
        name = getname(http_method) if operation is None else operation
        yield dict(
            method=http_method, name=name, doc=getdoc(function),
            op=operation, restful=(operation is None))


def describe_handler(handler):
    """Return a serialisable description of a handler.

    :type handler: :class:`OperationsHandler` or
        :class:`AnonymousOperationsHandler` instance or subclass.
    """
    # Want the class, not an instance.
    if isinstance(handler, BaseHandler):
        handler = type(handler)

    path = generate_doc(handler).resource_uri_template
    path = "" if path is None else path

    resource_uri = getattr(handler, "resource_uri", lambda: ())
    view_name, uri_params, uri_kw = merge(resource_uri(), (None, (), {}))
    assert uri_kw == {}, (
        "Resource URI specifications with keyword parameters are not yet "
        "supported: handler=%r; view_name=%r" % (handler, view_name))

    return {
        "actions": list(describe_actions(handler)),
        "doc": getdoc(handler),
        "name": handler.__name__,
        "params": uri_params,
        "path": path,
        }


def describe_resource(resource):
    """Return a serialisable description of a resource.

    :type resource: :class:`OperationsResource` instance.
    """
    authenticate = not any(
        isinstance(auth, NoAuthentication)
        for auth in resource.authentication)
    if authenticate:
        if resource.anonymous is None:
            anon = None
            auth = describe_handler(resource.handler)
        else:
            anon = describe_handler(resource.anonymous)
            auth = describe_handler(resource.handler)
    else:
        anon = describe_handler(resource.handler)
        auth = None
    name = anon["name"] if auth is None else auth["name"]
    return {"anon": anon, "auth": auth, "name": name}
