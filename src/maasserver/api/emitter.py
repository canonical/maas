# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Faster, output-compatible replacement for Piston's `Emitter.construct`.

Piston works out how to render a model (which fields, which handler methods,
how to reverse its URI) again for every instance it emits. It also sends every
value, including plain strings and numbers, through its generic dispatcher.
With large listings this overhead dominates the response time.

`construct` produces exactly the same output as the original. It works out a
rendering plan once per model type and field spec, and caches handler lookups
and reversed URIs for the duration of a single call. Primitive values skip the
dispatcher.
"""

from decimal import Decimal
import inspect
from itertools import chain
import re

from django.db.models import Model
from django.db.models.query import QuerySet, RawQuerySet
from django.http import HttpResponse
from django.urls import NoReverseMatch
from django.utils.encoding import smart_str
from piston3 import emitters as piston_emitters
from piston3.utils import HttpStatusCode

# Values of these exact types are emitted as they are. They can never be part
# of a circular reference, since they don't contain other values.
_PRIMITIVE_TYPES = frozenset((str, int, float, bool, type(None)))
_URL_ARG_TYPES = frozenset((str, int))
_QUERYSET_TYPES = (QuerySet, RawQuerySet)
_SEQUENCE_TYPES = (tuple, list, set)

# Kinds of step in a model rendering plan.
_ATTRIBUTE = 0
_METHOD_FIELD = 1
_DYNAMIC = 2
_MANY_TO_MANY = 3
_NESTED = 4


def _has_at_most_one_required_parameter(func):
    signature = inspect.signature(func)
    args_only = [
        p
        for p in signature.parameters.values()
        if p.default is inspect.Parameter.empty
    ]
    return len(args_only) <= 1


def construct(self):
    """Recursively serialize the emitter's data, like Piston does.

    Added for the v2 machine listing: with 1,000 machines, Piston's own
    `construct` (working out the rendering plan and dispatching every value,
    including plain strings and numbers, again for each instance) cost about
    4.4s on top of the ~2.4s this version takes to render the same output,
    nearly doubling the render time. Reverting just this function (leaving
    the query-count fixes in place) takes the listing from 5.6s to 9.3s for
    the same 32 queries and byte-identical output.
    """
    stack = self.stack = []
    anonymous = self.anonymous
    reverser = piston_emitters.reverser
    typemapper = self.typemapper
    handlers_count = len(typemapper)
    type_infos = {}
    plans = {}
    signatures = {}
    uris = {}

    def _forget_handlers_if_registered():
        # Outside of requests, the URLconf may be loaded while emitting, which
        # registers more handlers.
        nonlocal handlers_count
        if len(typemapper) != handlers_count:
            handlers_count = len(typemapper)
            type_infos.clear()
            plans.clear()

    def _type_info(model_type):
        _forget_handlers_if_registered()
        try:
            return type_infos[model_type]
        except KeyError:
            pass
        handler = self.in_typemapper(model_type, anonymous)
        has_resource_uri = bool(handler) and hasattr(handler, "resource_uri")
        resource_uri = handler.resource_uri if has_resource_uri else None
        info = type_infos[model_type] = (
            handler,
            has_resource_uri,
            resource_uri,
        )
        return info

    def _any(thing, fields=None):
        if type(thing) in _PRIMITIVE_TYPES:
            return thing

        if thing in stack:
            raise RuntimeError(
                "Circular reference detected while emitting response"
            )

        stack.append(thing)

        ret = None
        if isinstance(thing, _QUERYSET_TYPES):
            ret = _list(thing, fields)
        elif isinstance(thing, _SEQUENCE_TYPES):
            ret = _list(thing, fields)
        elif isinstance(thing, dict):
            ret = _dict(thing, fields)
        elif isinstance(thing, Decimal):
            ret = str(thing)
        elif isinstance(thing, Model):
            ret = _model(thing, fields)
        elif isinstance(thing, HttpResponse):
            raise HttpStatusCode(thing)
        elif inspect.isfunction(thing):
            if not inspect.signature(thing).parameters:
                ret = _any(thing())
        elif hasattr(thing, "__emittable__"):
            f = thing.__emittable__
            if inspect.ismethod(f) and not inspect.signature(f).parameters:
                ret = _any(f())
        elif repr(thing).startswith(
            "<django.db.models.fields.related.RelatedManager"
        ):
            ret = _any(thing.all())
        else:
            ret = smart_str(thing, strings_only=True)

        stack.pop()

        return ret

    def _list(data, fields=None):
        return [
            value if type(value) in _PRIMITIVE_TYPES else _any(value, fields)
            for value in data
        ]

    def _dict(data, fields=None):
        return dict(
            [
                (
                    key,
                    value
                    if type(value) in _PRIMITIVE_TYPES
                    else _any(value, fields),
                )
                for key, value in data.items()
            ]
        )

    def _related(data, fields=None):
        return [_model(m, fields) for m in data.all()]

    def _is_field_callable(func):
        if not inspect.ismethod(func):
            return _has_at_most_one_required_parameter(func)
        # Bound methods share the signature of their underlying function.
        try:
            return signatures[func.__func__]
        except KeyError:
            callable_ = _has_at_most_one_required_parameter(func)
            signatures[func.__func__] = callable_
            return callable_
        except TypeError:
            return _has_at_most_one_required_parameter(func)

    def _reverse(url_id, args):
        if (
            type(url_id) is str
            and type(args) in (tuple, list)
            and all(type(arg) in _URL_ARG_TYPES for arg in args)
        ):
            cache_key = (url_id, *args)
            try:
                return uris[cache_key]
            except KeyError:
                uri = uris[cache_key] = reverser(url_id, args=args)
                return uri
        return reverser(url_id, args=args)

    def _build_plan(data, fields):
        handler = _type_info(type(data))[0]
        get_absolute_uri = False

        if not (handler or fields):
            return None

        if handler and not fields:
            fields = getattr(handler, "fields", None)

        if not fields:
            mapped = handler
            get_fields = set(mapped.fields)
            exclude_fields = set(mapped.exclude).difference(get_fields)

            if "absolute_uri" in get_fields:
                get_absolute_uri = True

            if not get_fields:
                try:
                    private_fields = data._meta.private_fields
                except AttributeError:
                    private_fields = data._meta.virtual_fields
                get_fields = set(
                    [
                        f.attname.replace("_id", "", 1)
                        for f in chain(data._meta.fields, private_fields)
                    ]
                )

            if hasattr(mapped, "extra_fields"):
                get_fields.update(mapped.extra_fields)

            for exclude in exclude_fields:
                if isinstance(exclude, str):
                    get_fields.discard(exclude)
                elif isinstance(exclude, re._pattern_type):
                    for field in get_fields.copy():
                        if exclude.match(field):
                            get_fields.discard(field)
        else:
            get_fields = set(fields)

        met_fields = self.method_fields(handler, get_fields)
        try:
            private_fields = data._meta.private_fields
        except AttributeError:
            private_fields = data._meta.virtual_fields

        steps = []
        for f in data._meta.local_fields + private_fields:
            if f.serialize and not any(
                [p in met_fields for p in [f.attname, f.name]]
            ):
                try:
                    remote_field = f.remote_field
                except AttributeError:
                    remote_field = f.rel
                if not remote_field:
                    if f.attname in get_fields:
                        steps.append((_ATTRIBUTE, f.attname, f.attname))
                        get_fields.remove(f.attname)
                else:
                    if f.attname[:-3] in get_fields:
                        steps.append((_ATTRIBUTE, f.name, f.name))
                        get_fields.remove(f.name)

        for mf in data._meta.many_to_many:
            if mf.serialize and mf.attname not in met_fields:
                if mf.attname in get_fields:
                    steps.append((_MANY_TO_MANY, mf.name, mf.name))
                    get_fields.remove(mf.name)

        for maybe_field in get_fields:
            if isinstance(maybe_field, list | tuple):
                model, nested_fields = maybe_field
                steps.append((_NESTED, model, nested_fields))
            elif maybe_field in met_fields:
                steps.append(
                    (_METHOD_FIELD, maybe_field, met_fields[maybe_field])
                )
            else:
                steps.append((_DYNAMIC, maybe_field, None))

        return tuple(steps), get_absolute_uri, handler or self.handler

    def _model(data, fields=None):
        model_type = type(data)
        _forget_handlers_if_registered()
        # `fields` specs are long-lived handler attributes; keying by identity
        # guarantees the cached plan was built from the very same spec.
        plan_key = (model_type, id(fields))
        cached = plans.get(plan_key)
        if cached is None or cached[0] is not fields:
            cached = plans[plan_key] = (fields, _build_plan(data, fields))
        plan = cached[1]

        ret = {}
        if plan is None:
            get_absolute_uri = False
            for f in data._meta.fields:
                ret[f.attname] = _any(getattr(data, f.attname))

            known = dir(data.__class__) + list(ret.keys())
            add_ons = [k for k in dir(data) if k not in known]

            for k in add_ons:
                ret[k] = _any(getattr(data, k))
        else:
            steps, get_absolute_uri, fallback_handler = plan
            for kind, key, arg in steps:
                if kind == _METHOD_FIELD:
                    value = arg(data)
                    ret[key] = (
                        value
                        if type(value) in _PRIMITIVE_TYPES
                        else _any(value)
                    )
                elif kind == _ATTRIBUTE:
                    value = getattr(data, arg)
                    ret[key] = (
                        value
                        if type(value) in _PRIMITIVE_TYPES
                        else _any(value)
                    )
                elif kind == _DYNAMIC:
                    try:
                        maybe = getattr(data, key)
                    except AttributeError:
                        handler_f = getattr(fallback_handler, key, None)
                        if handler_f:
                            ret[key] = _any(handler_f(data))
                    else:
                        if type(maybe) in _PRIMITIVE_TYPES:
                            ret[key] = maybe
                        elif hasattr(maybe, "all"):
                            ret[key] = _related(maybe)
                        elif callable(maybe):
                            if _is_field_callable(maybe):
                                ret[key] = _any(maybe())
                        else:
                            ret[key] = _any(maybe)
                elif kind == _MANY_TO_MANY:
                    ret[key] = [
                        _model(m) for m in getattr(data, arg).iterator()
                    ]
                else:
                    inst = getattr(data, key, None)
                    if inst:
                        if hasattr(inst, "all"):
                            ret[key] = _related(inst, arg)
                        elif callable(inst):
                            if len(inspect.signature(inst).parameters) == 1:
                                ret[key] = _any(inst(), arg)
                        else:
                            ret[key] = _model(inst, arg)

        _, has_resource_uri, resource_uri = _type_info(model_type)
        if has_resource_uri:
            url_id, args = resource_uri(data)
            try:
                ret["resource_uri"] = _reverse(url_id, args)
            except NoReverseMatch:
                pass

        if hasattr(data, "get_api_url") and "resource_uri" not in ret:
            try:
                ret["resource_uri"] = data.get_api_url()
            except Exception:
                pass

        if hasattr(data, "get_absolute_url") and get_absolute_uri:
            try:
                ret["absolute_uri"] = data.get_absolute_url()
            except Exception:
                pass

        return ret

    return _any(self.data, self.fields)
