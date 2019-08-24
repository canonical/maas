# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities to help document/describe the public facing API."""

__all__ = [
    "describe_api",
    "describe_handler",
    "describe_resource",
    "find_api_resources",
    "generate_api_docs",
    "get_api_description_hash",
    ]

from collections import (
    Mapping,
    Sequence,
)
from functools import partial
import hashlib
from inspect import getdoc
from io import StringIO
from itertools import zip_longest
import json
from threading import RLock

from django.core.urlresolvers import (
    get_resolver,
    RegexURLPattern,
    RegexURLResolver,
)
from maasserver.api.annotations import APIDocstringParser
from piston3.authentication import NoAuthentication
from piston3.doc import generate_doc
from piston3.handler import BaseHandler
from piston3.resource import Resource
from provisioningserver.drivers.pod.registry import PodDriverRegistry
from provisioningserver.drivers.power.registry import PowerDriverRegistry


def accumulate_api_resources(resolver, accumulator):
    """Accumulate handlers from the given resolver.

    Handlers are of type :class:`HandlerMetaClass`, and must define a
    `resource_uri` method.

    Handlers that have the attribute hidden set to True, will not be returned.

    :rtype: Generator, yielding handlers.
    """
    p_has_resource_uri = lambda resource: (
        getattr(resource.handler, "resource_uri", None) is not None)
    p_is_not_hidden = lambda resource: (
        getattr(resource.handler, "hidden", False))
    for pattern in resolver.url_patterns:
        if isinstance(pattern, RegexURLResolver):
            accumulate_api_resources(pattern, accumulator)
        elif isinstance(pattern, RegexURLPattern):
            if isinstance(pattern.callback, Resource):
                resource = pattern.callback
                if p_has_resource_uri(resource) and \
                        not p_is_not_hidden(resource):
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


def generate_power_types_doc():
    """Generate ReST documentation for the supported power types.

    The documentation is derived from the `PowerDriverRegistry`.
    """
    output = StringIO()
    line = partial(print, file=output)

    line('Power types')
    line('```````````')
    line()
    line("This is the list of the supported power types and their "
         "associated power parameters.  Note that the list of usable "
         "power types for a particular rack controller might be a subset of "
         "this list if the rack controller in question is from an older "
         "version of MAAS.")
    line()
    for _, driver in PowerDriverRegistry:
        title = "%s (%s)" % (driver.name, driver.description)
        line(title)
        line('=' * len(title))
        line('')
        line("Power parameters:")
        line('')
        for field in driver.settings:
            field_description = []
            field_description.append(
                "* %s (%s)." % (field['name'], field['label']))
            choices = field.get('choices', [])
            if len(choices) > 0:
                field_description.append(
                    " Choices: %s" % ', '.join(
                        "'%s' (%s)" % (choice[0], choice[1])
                        for choice in choices))
            default = field.get('default', '')
            if default != '':
                field_description.append("  Default: '%s'." % default)
            line(''.join(field_description))
        line('')
    return output.getvalue()


def generate_pod_types_doc():
    """Generate ReST documentation for the supported pod types.

    The documentation is derived from the `PodDriverRegistry`.
    """
    output = StringIO()
    line = partial(print, file=output)

    line('Pod types')
    line('`````````')
    line()
    line("This is the list of the supported pod types and their "
         "associated parameters.  Note that the list of usable pod types "
         "for a particular rack controller might be a subset of this "
         "list if the rack controller in question is from an older version of "
         "MAAS.")
    line()
    for _, driver in PodDriverRegistry:
        title = "%s (%s)" % (driver.name, driver.description)
        line(title)
        line('=' * len(title))
        line('')
        line("Parameters:")
        line('')
        for field in driver.settings:
            field_description = []
            field_description.append(
                "* %s (%s)." % (field['name'], field['label']))
            choices = field.get('choices', [])
            if len(choices) > 0:
                field_description.append(
                    " Choices: %s" % ', '.join(
                        "'%s' (%s)" % (choice[0], choice[1])
                        for choice in choices))
            default = field.get('default', '')
            if default != '':
                field_description.append("  Default: '%s'." % default)
            line(''.join(field_description))
        line('')
    return output.getvalue()


def generate_api_docs(resources):
    """Generate ReST documentation objects for the ReST API.

    Yields Piston Documentation objects describing the given resources.

    This also ensures that handlers define 'resource_uri' methods. This is
    easily forgotten and essential in order to generate proper documentation.

    :return: Generates :class:`piston.doc.HandlerDocumentation` instances.
    """
    sentinel = object()
    resource_key = (
        lambda resource: resource.handler.__class__.__name__)
    for resource in sorted(resources, key=resource_key):
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
    for values in zip_longest(*iterables, fillvalue=undefined):
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
    from maasserver.api import support  # Circular import.
    getname = support.OperationsResource.crudmap.get
    for signature, function in handler.exports.items():
        http_method, operation = signature
        name = getname(http_method) if operation is None else operation

        ap = APIDocstringParser()
        doc = getdoc(function)

        if doc is not None:
            if APIDocstringParser.is_annotated_docstring(doc):
                # Because the docstring contains annotations, we
                # need to construct a string suitable for output
                # to stdout that matches the style used for
                # non-annotated docstrings in the CLI.
                ap.parse(doc)
                ap_dict = ap.get_dict()
                description = ap_dict['description'].rstrip()
                description_title = ap_dict['description_title'].rstrip()
                if description_title != "":
                    doc = description_title + "\n\n"
                    doc += description + "\n\n"
                else:
                    doc = description + "\n\n"

                # Here, we add the params, but we skip params
                # surrounded by curly brackets (e.g. {foo})
                # because these indicate params that appear in
                # the URI (e.g. /zone/{name}/). I.e. positional
                # arguments. These already appear in the CLI
                # help command output so we don't want duplicates.
                for param in ap_dict['params']:
                    pname = param['name']
                    if pname.find("{") == -1 and pname.find("}") == -1:
                        required = "Required. "
                        if param['options']['required'] == "false":
                            required = "Optional. "

                        param_description = param['description'].rstrip()

                        doc += (":param %s: %s%s\n" %
                                (pname, required, param_description))
                        doc += (":type %s: %s\n\n " % (pname, param['type']))

        yield dict(
            method=http_method, name=name, doc=doc,
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
        "params": tuple(uri_params),
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
        else:
            anon = describe_handler(resource.anonymous)
        auth = describe_handler(resource.handler)
        name = auth["name"]
    else:
        anon = describe_handler(resource.handler)
        auth = None
        name = anon["name"]
    return {"anon": anon, "auth": auth, "name": name}


def describe_api():
    """Return a description of the whole MAAS API.

    :return: An object describing the whole MAAS API. Links to the API will
        not be absolute; they will be relative, and independent of the medium
        over which this description was obtained.
    """
    from maasserver import urls_api as urlconf

    # This is the core of it:
    description = {
        "doc": "MAAS API",
        "resources": [
            describe_resource(resource)
            for resource in find_api_resources(urlconf)
        ],
    }

    # However, for backward compatibility, add "handlers" as an alias for all
    # not-None anon and auth handlers in "resources".
    description["handlers"] = []
    description["handlers"].extend(
        resource["anon"] for resource in description["resources"]
        if resource["anon"] is not None)
    description["handlers"].extend(
        resource["auth"] for resource in description["resources"]
        if resource["auth"] is not None)

    return description


class KeyCanonicalNone:
    """See `key_canonical`."""

    def __lt__(self, other):
        if isinstance(other, KeyCanonicalNone):
            return False
        else:
            return True

    def __eq__(self, other):
        if isinstance(other, KeyCanonicalNone):
            return True
        else:
            return False


class KeyCanonicalNumeric:
    """See `key_canonical`."""

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        if isinstance(other, KeyCanonicalNone):
            return False
        elif isinstance(other, KeyCanonicalNumeric):
            return self.value < other.value
        else:
            return True

    def __eq__(self, other):
        if isinstance(other, KeyCanonicalNumeric):
            return self.value == other.value
        else:
            return False


class KeyCanonicalString:
    """See `key_canonical`."""

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        if isinstance(other, KeyCanonicalString):
            return self.value < other.value
        elif isinstance(other, KeyCanonicalTuple):
            return True
        else:
            return False

    def __eq__(self, other):
        if isinstance(other, KeyCanonicalString):
            return self.value == other.value
        else:
            return False


class KeyCanonicalTuple:
    """See `key_canonical`."""

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        if isinstance(other, KeyCanonicalTuple):
            return self.value < other.value
        else:
            return False

    def __eq__(self, other):
        if isinstance(other, KeyCanonicalTuple):
            return self.value == other.value
        else:
            return False


def key_canonical(value):
    """Create a sort key for the canonical API description.

    For a limited set of types, this provides Python 2-like sorting. For
    example, it is possible to compare ``None`` with a string. Types compare
    like so:

      None < Numeric/Boolean < String < Tuple

    Within each type, comparisons happen as normal. Use with ``sort`` or
    ``sorted``::

      sorted(things, key=key_canonical)

    :raise TypeError: For types that cannot be compared.
    """
    if value is None:
        return KeyCanonicalNone()
    elif isinstance(value, (bool, int, float)):
        return KeyCanonicalNumeric(value)
    elif isinstance(value, str):
        return KeyCanonicalString(value)
    elif isinstance(value, tuple):
        return KeyCanonicalTuple(
            tuple(key_canonical(v) for v in value))
    else:
        raise TypeError(
            "Cannot compare %r (%s)" % (
                value, type(value).__qualname__))


def describe_canonical(description):
    """Returns an ordered data structure composed from limited types.

    Specifically:

    * Elements in lists are described, recursively, by this function, then
      sorted into a tuple.

    * Keys and values in dicts are described, recursively, by this function,
      then captured as (key, value) tuples, then sorted into a tuple.

    * Byte strings are decoded from UTF-8.

    * Unicode strings are passed through.

    * True, False, and None are passed through.

    * Anything else causes a `TypeError`.

    """
    if description in (True, False, None):
        return description
    if isinstance(description, (int, float)):
        return description
    elif isinstance(description, bytes):
        return description.decode("utf-8")
    elif isinstance(description, str):
        return description
    elif isinstance(description, Sequence):
        return tuple(sorted(
            (describe_canonical(element)
             for element in description),
            key=key_canonical))
    elif isinstance(description, Mapping):
        return tuple(sorted(
            ((describe_canonical(key), describe_canonical(value))
             for (key, value) in sorted(description.items())),
            key=key_canonical))
    else:
        raise TypeError(
            "Cannot produce canonical representation for %r."
            % (description,))


def hash_canonical(description):
    """Return an SHA-1 HASH object seeded with `description`.

    Specifically, `description` is converted to a canonical representation by
    `describe_canonical`, dumped as JSON, encoded as a byte string, then fed
    into a new `hashlib.sha1` object.
    """
    description = describe_canonical(description)
    description_as_json = json.dumps(description)
    # Python 3's json.dumps returns a `str`, so encode if necessary.
    if not isinstance(description_as_json, bytes):
        description_as_json = description_as_json.encode("ascii")
    # We /could/ instead pass a hashing object in and call .update()...
    return hashlib.sha1(description_as_json)


api_description_hash = None
api_description_hash_lock = RLock()


def get_api_description_hash():
    """Return a hash for the current API description."""

    global api_description_hash
    global api_description_hash_lock

    if api_description_hash is None:
        with api_description_hash_lock:
            if api_description_hash is None:
                api_description = describe_api()
                api_description_hasher = hash_canonical(api_description)
                api_description_hash = api_description_hasher.hexdigest()

    # The hash is an immutable string, so safe to return directly.
    return api_description_hash
