# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities to help document/describe the public facing API."""

__all__ = [
    "find_api_resources",
    "generate_api_docs",
]

from collections.abc import Mapping, Sequence
from functools import lru_cache, partial
import hashlib
from inspect import getdoc
from io import StringIO
from itertools import zip_longest
import json
from operator import itemgetter

from django.urls import get_resolver, URLPattern, URLResolver
from piston3.authentication import NoAuthentication
from piston3.doc import generate_doc
from piston3.handler import BaseHandler
from piston3.resource import Resource

from maasserver.api.annotations import APIDocstringParser
from provisioningserver.drivers.pod.registry import PodDriverRegistry
from provisioningserver.drivers.power.registry import PowerDriverRegistry


@lru_cache(maxsize=1)
def get_api_description():
    """Return the API description"""
    description = _describe_api()
    description["hash"] = _get_api_description_hash(description)
    return description


def find_api_resources(urlconf=None):
    """Find the API resources defined in `urlconf`.

    :rtype: :class:`set` of :class:`Resource` instances.
    """
    resolver = get_resolver(urlconf)
    resources = set()
    _accumulate_api_resources(resolver, resources)
    return resources


def generate_power_types_doc():
    """Generate ReST documentation for the supported power types.

    The documentation is derived from the `PowerDriverRegistry`.
    """
    output = StringIO()
    line = partial(print, file=output)

    line("Power types")
    line("```````````")
    line()
    line(
        "This is the list of the supported power types and their "
        "associated power parameters.  Note that the list of usable "
        "power types for a particular rack controller might be a subset of "
        "this list if the rack controller in question is from an older "
        "version of MAAS."
    )
    line()
    for _, driver in PowerDriverRegistry:
        title = f"{driver.name} ({driver.description})"
        line(title)
        line("=" * len(title))
        line("")
        line("Power parameters:")
        line("")
        for field in driver.settings:
            field_description = []
            field_description.append(
                "* {} ({}).".format(field["name"], field["label"])
            )
            choices = field.get("choices", [])
            if len(choices) > 0:
                field_description.append(
                    " Choices: %s"
                    % ", ".join(
                        f"'{choice[0]}' ({choice[1]})" for choice in choices
                    )
                )
            default = field.get("default", "")
            if default != "":
                field_description.append("  Default: '%s'." % default)
            line("".join(field_description))
        line("")
    return output.getvalue()


def generate_pod_types_doc():
    """Generate ReST documentation for the supported pod types.

    The documentation is derived from the `PodDriverRegistry`.
    """
    output = StringIO()
    line = partial(print, file=output)

    line("Pod types")
    line("`````````")
    line()
    line(
        "This is the list of the supported pod types and their "
        "associated parameters.  Note that the list of usable pod types "
        "for a particular rack controller might be a subset of this "
        "list if the rack controller in question is from an older version of "
        "MAAS."
    )
    line()
    for _, driver in PodDriverRegistry:
        title = f"{driver.name} ({driver.description})"
        line(title)
        line("=" * len(title))
        line("")
        line("Parameters:")
        line("")
        for field in driver.settings:
            field_description = []
            field_description.append(
                "* {} ({}).".format(field["name"], field["label"])
            )
            choices = field.get("choices", [])
            if len(choices) > 0:
                field_description.append(
                    " Choices: %s"
                    % ", ".join(
                        f"'{choice[0]}' ({choice[1]})" for choice in choices
                    )
                )
            default = field.get("default", "")
            if default != "":
                field_description.append("  Default: '%s'." % default)
            line("".join(field_description))
        line("")
    return output.getvalue()


def generate_api_docs(resources):
    """Generate ReST documentation objects for the ReST API.

    Yields Piston Documentation objects describing the given resources.

    This also ensures that handlers define 'resource_uri' methods. This is
    easily forgotten and essential in order to generate proper documentation.

    :return: Generates :class:`piston.doc.HandlerDocumentation` instances.
    """
    sentinel = object()

    def resource_key(resource):
        return resource.handler.__class__.__name__

    for resource in sorted(resources, key=resource_key):
        handler = type(resource.handler)
        if getattr(handler, "resource_uri", sentinel) is sentinel:
            raise AssertionError(
                "Missing resource_uri in %s" % handler.__name__
            )
        yield generate_doc(handler)


def _accumulate_api_resources(resolver, accumulator):
    """Add handlers from the resolver to the accumulator set.

    Handlers are of type :class:`HandlerMetaClass`, and must define a
    `resource_uri` method.

    Handlers that have the attribute hidden set to True, will not be returned.
    """

    def visible(handler):
        return bool(
            getattr(handler, "resource_uri", None)
            and not getattr(handler, "hidden", False)
        )

    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            _accumulate_api_resources(pattern, accumulator)
        elif isinstance(pattern, URLPattern):
            if isinstance(pattern.callback, Resource) and visible(
                pattern.callback.handler
            ):
                accumulator.add(pattern.callback)
        else:
            raise AssertionError(
                f"Not a recognised pattern or resolver: {pattern!r}"
            )


def _merge(*iterables):
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


def _describe_actions(handler):
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
    from maasserver.api import support

    getname = support.OperationsResource.crudmap.get

    actions = []

    # ensure stable sorting, accounting for operation being None
    exports = sorted(
        handler.exports.items(),
        key=lambda item: (item[0][0], item[0][1] or ""),
    )
    for signature, function in exports:
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
                description = ap_dict["description"].rstrip()
                description_title = ap_dict["description_title"].rstrip()
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
                for param in ap_dict["params"]:
                    pname = param["name"]
                    if pname.find("{") == -1 and pname.find("}") == -1:
                        required = "Required. "
                        if param["options"]["required"] == "false":
                            required = "Optional. "

                        param_description = param["description"].rstrip()

                        doc += ":param {}: {}{}\n".format(
                            pname,
                            required,
                            param_description,
                        )
                        doc += ":type {}: {}\n\n ".format(pname, param["type"])

        actions.append(
            {
                "method": http_method,
                "name": name,
                "doc": doc,
                "op": operation,
                "restful": operation is None,
            }
        )
    return sorted(actions, key=itemgetter("name"))


def _describe_handler(handler):
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
    view_name, uri_params, uri_kw = _merge(resource_uri(), (None, (), {}))
    assert uri_kw == {}, (
        "Resource URI specifications with keyword parameters are not yet "
        "supported: handler=%r; view_name=%r" % (handler, view_name)
    )

    return {
        "actions": _describe_actions(handler),
        "doc": getdoc(handler),
        "name": handler.__name__,
        "params": tuple(uri_params),
        "path": path,
    }


def _describe_resource(resource):
    """Return a serialisable description of a resource.

    :type resource: :class:`OperationsResource` instance.
    """
    authenticate = not any(
        isinstance(auth, NoAuthentication) for auth in resource.authentication
    )
    if authenticate:
        if resource.anonymous is None:
            anon = None
        else:
            anon = _describe_handler(resource.anonymous)
        auth = _describe_handler(resource.handler)
        name = auth["name"]
    else:
        anon = _describe_handler(resource.handler)
        auth = None
        name = anon["name"]
    return {"anon": anon, "auth": auth, "name": name}


def _describe_api():
    """Return a description of the whole MAAS API.

    :return: An object describing the whole MAAS API. Links to the API will
        not be absolute; they will be relative, and independent of the medium
        over which this description was obtained.
    """
    from maasserver import urls_api as urlconf

    resources = sorted(
        (
            _describe_resource(resource)
            for resource in find_api_resources(urlconf)
        ),
        key=itemgetter("name"),
    )
    # This is the core of it:
    description = {
        "doc": "MAAS API",
        "resources": resources,
    }
    # However, for backward compatibility, add "handlers" as an alias for all
    # not-None anon and auth handlers in "resources".
    description["handlers"] = []
    description["handlers"].extend(
        resource["anon"]
        for resource in resources
        if resource["anon"] is not None
    )
    description["handlers"].extend(
        resource["auth"]
        for resource in resources
        if resource["auth"] is not None
    )

    return description


class KeyCanonicalNone:
    """See `_key_canonical`."""

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
    """See `_key_canonical`."""

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
    """See `_key_canonical`."""

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
    """See `_key_canonical`."""

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


def _key_canonical(value):
    """Create a sort key for the canonical API description.

    For a limited set of types, this provides Python 2-like sorting. For
    example, it is possible to compare ``None`` with a string. Types compare
    like so:

      None < Numeric/Boolean < String < Tuple

    Within each type, comparisons happen as normal. Use with ``sort`` or
    ``sorted``::

      sorted(things, key=_key_canonical)

    :raise TypeError: For types that cannot be compared.
    """
    if value is None:
        return KeyCanonicalNone()
    elif isinstance(value, (bool, int, float)):
        return KeyCanonicalNumeric(value)
    elif isinstance(value, str):
        return KeyCanonicalString(value)
    elif isinstance(value, tuple):
        return KeyCanonicalTuple(tuple(_key_canonical(v) for v in value))
    else:
        raise TypeError(
            f"Cannot compare {value!r} ({type(value).__qualname__})"
        )


def _describe_canonical(description):
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
        return tuple(
            sorted(
                (_describe_canonical(element) for element in description),
                key=_key_canonical,
            )
        )
    elif isinstance(description, Mapping):
        return tuple(
            sorted(
                (
                    (_describe_canonical(key), _describe_canonical(value))
                    for (key, value) in sorted(description.items())
                ),
                key=_key_canonical,
            )
        )
    else:
        raise TypeError(
            f"Cannot produce canonical representation for {description!r}."
        )


def _hash_canonical(description):
    """Return an SHA-1 HASH object seeded with `description`.

    Specifically, `description` is converted to a canonical representation by
    `_describe_canonical`, dumped as JSON, encoded as a byte string, then fed
    into a new `hashlib.sha1` object.
    """
    description = _describe_canonical(description)
    description_as_json = json.dumps(description).encode("ascii")
    return hashlib.sha1(description_as_json)


def _get_api_description_hash(description):
    """Return the SHA-1 hash for the API description."""
    hasher = _hash_canonical(description)
    return hasher.hexdigest()
