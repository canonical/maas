import decimal
import inspect
import io
from itertools import chain
import json
import pickle
import re
from typing import ClassVar

from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model
from django.db.models.query import (
    QuerySet,
    RawQuerySet,
)
from django.http import HttpResponse
from django.urls import (
    NoReverseMatch,
    reverse,
)
from django.utils.encoding import smart_str
from django.utils.xmlutils import SimplerXMLGenerator
import yaml

from .utils import (
    HttpStatusCode,
    Mimer,
)
from .validate_jsonp import is_valid_jsonp_callback_value

# Allow people to change the reverser (default `permalink`).
reverser = reverse


class Emitter:
    """
    Super emitter. All other emitters should subclass
    this one. It has the `construct` method which
    conveniently returns a serialized `dict`. This is
    usually the only method you want to use in your
    emitter. See below for examples.

    `RESERVED_FIELDS` was introduced when better resource
    method detection came, and we accidentially caught these
    as the methods on the handler. Issue58 says that's no good.
    """

    EMITTERS: ClassVar[dict] = {}
    RESERVED_FIELDS = frozenset(
        [
            "read",
            "update",
            "create",
            "delete",
            "model",
            "anonymous",
            "allowed_methods",
            "fields",
            "exclude",
        ]
    )

    def __init__(
        self, payload, typemapper, handler, fields=(), anonymous=True
    ):
        self.typemapper = typemapper
        self.data = payload
        self.handler = handler
        self.fields = fields
        self.anonymous = anonymous

        if isinstance(self.data, Exception):
            raise

    def method_fields(self, handler, fields):
        if not handler:
            return {}

        ret = dict()

        for field in fields - Emitter.RESERVED_FIELDS:
            t = getattr(handler, str(field), None)

            if t and callable(t):
                ret[field] = t

        return ret

    def construct(self):
        """
        Recursively serialize a lot of types, and
        in cases where it doesn't recognize the type,
        it will fall back to Django's `smart_str`.

        Returns `dict`.
        """

        def _any(thing, fields=None):
            """
            Dispatch, all types are routed through here.
            """
            ret = None

            # return anything we've already seen as a string only
            # this prevents infinite recursion in the case of recursive
            # relationships

            if thing in self.stack:
                raise RuntimeError(
                    "Circular reference detected while emitting " "response"
                )

            self.stack.append(thing)

            if isinstance(thing, QuerySet | RawQuerySet):
                ret = _qs(thing, fields)
            elif isinstance(thing, tuple | list | set):
                ret = _list(thing, fields)
            elif isinstance(thing, dict):
                ret = _dict(thing, fields)
            elif isinstance(thing, decimal.Decimal):
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

            self.stack.pop()

            return ret

        def _fk(data, field):
            """
            Foreign keys.
            """
            return _any(getattr(data, field.name))

        def _related(data, fields=None):
            """
            Foreign keys.
            """
            return [_model(m, fields) for m in data.all()]

        def _m2m(data, field, fields=None):
            """
            Many to many (re-route to `_model`.)
            """
            return [
                _model(m, fields) for m in getattr(data, field.name).iterator()
            ]

        def _model(data, fields=None):
            """
            Models. Will respect the `fields` and/or
            `exclude` on the handler (see `typemapper`.)
            """
            ret = {}
            handler = self.in_typemapper(type(data), self.anonymous)
            get_absolute_uri = False

            if handler or fields:
                # FIXME
                # Catch 22 here. Either we use the fields from the
                # typemapped handler to make nested models work but the
                # declared list_fields will ignored for models, or we
                # use the list_fields from the base handler and accept that
                # the nested models won't appear properly
                # Refs #157
                if handler and not fields:
                    fields = getattr(handler, "fields", None)

                if not fields:
                    """
                    Fields was not specified, try to find teh correct
                    version in the typemapper we were sent.
                    """
                    mapped = self.in_typemapper(type(data), self.anonymous)
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
                                for f in chain(
                                    data._meta.fields, private_fields
                                )
                            ]
                        )

                    if hasattr(mapped, "extra_fields"):
                        get_fields.update(mapped.extra_fields)

                    # sets can be negated.
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
                                ret[f.attname] = _any(getattr(data, f.attname))
                                get_fields.remove(f.attname)
                        else:
                            if f.attname[:-3] in get_fields:
                                ret[f.name] = _fk(data, f)
                                get_fields.remove(f.name)

                for mf in data._meta.many_to_many:
                    if mf.serialize and mf.attname not in met_fields:
                        if mf.attname in get_fields:
                            ret[mf.name] = _m2m(data, mf)
                            get_fields.remove(mf.name)

                # try to get the remainder of fields
                for maybe_field in get_fields:
                    if isinstance(maybe_field, list | tuple):
                        model, fields = maybe_field
                        inst = getattr(data, model, None)

                        if inst:
                            if hasattr(inst, "all"):
                                ret[model] = _related(inst, fields)
                            elif callable(inst):
                                if (
                                    len(inspect.signature(inst).parameters)
                                    == 1
                                ):
                                    ret[model] = _any(inst(), fields)
                            else:
                                ret[model] = _model(inst, fields)

                    elif maybe_field in met_fields:
                        # Overriding normal field which has a "resource method"
                        # so you can alter the contents of certain fields without
                        # using different names.
                        ret[maybe_field] = _any(met_fields[maybe_field](data))

                    else:
                        try:
                            maybe = getattr(data, maybe_field)
                        except AttributeError:
                            maybe = None
                            handler_f = getattr(
                                handler or self.handler, maybe_field, None
                            )

                            if handler_f:
                                ret[maybe_field] = _any(handler_f(data))
                        else:
                            if hasattr(maybe, "all"):
                                ret[maybe_field] = _related(maybe)
                            elif callable(maybe):
                                signature = inspect.signature(maybe)
                                args_only = [
                                    p
                                    for p in signature.parameters.values()
                                    if p.default is inspect.Parameter.empty
                                ]
                                if len(args_only) <= 1:
                                    ret[maybe_field] = _any(maybe())
                            else:
                                ret[maybe_field] = _any(maybe)
            else:
                for f in data._meta.fields:
                    ret[f.attname] = _any(getattr(data, f.attname))

                fields = dir(data.__class__) + list(ret.keys())
                add_ons = [k for k in dir(data) if k not in fields]

                for k in add_ons:
                    ret[k] = _any(getattr(data, k))

            # resouce uri
            handler = self.in_typemapper(type(data), self.anonymous)
            if handler:
                if hasattr(handler, "resource_uri"):
                    url_id, fields = handler.resource_uri(data)

                    try:
                        ret["resource_uri"] = reverser(url_id, args=fields)
                    except NoReverseMatch:
                        pass

            if hasattr(data, "get_api_url") and "resource_uri" not in ret:
                try:
                    ret["resource_uri"] = data.get_api_url()
                except Exception:
                    pass

            # absolute uri
            if hasattr(data, "get_absolute_url") and get_absolute_uri:
                try:
                    ret["absolute_uri"] = data.get_absolute_url()
                except Exception:
                    pass

            return ret

        def _qs(data, fields=None):
            """
            Querysets.
            """
            return [_any(v, fields) for v in data]

        def _list(data, fields=None):
            """
            Lists.
            """
            return [_any(v, fields) for v in data]

        def _dict(data, fields=None):
            """
            Dictionaries.
            """
            return dict([(k, _any(v, fields)) for k, v in data.items()])

        # Kickstart the seralizin'.
        self.stack = []
        return _any(self.data, self.fields)

    def in_typemapper(self, model, anonymous):
        for klass, (km, is_anon) in self.typemapper.items():
            if model is km and is_anon is anonymous:
                return klass

    def render(self):
        """
        This super emitter does not implement `render`,
        this is a job for the specific emitter below.
        """
        raise NotImplementedError("Please implement render.")

    def stream_render(self, request, stream=True):
        """
        Tells our patched middleware not to look
        at the contents, and returns a generator
        rather than the buffered string. Should be
        more memory friendly for large datasets.
        """
        yield self.render(request)

    @classmethod
    def get(cls, format):
        """
        Gets an emitter, returns the class and a content-type.
        """
        if format in cls.EMITTERS:
            return cls.EMITTERS.get(format)

        raise ValueError(f"No emitters found for type {format}")

    @classmethod
    def register(cls, name, klass, content_type="text/plain"):
        """
        Register an emitter.

        Parameters::
         - `name`: The name of the emitter ('json', 'xml', 'yaml', ...)
         - `klass`: The emitter class.
         - `content_type`: The content type to serve response as.
        """
        cls.EMITTERS[name] = (klass, content_type)

    @classmethod
    def unregister(cls, name):
        """
        Remove an emitter from the registry. Useful if you don't
        want to provide output in one of the built-in emitters.
        """
        return cls.EMITTERS.pop(name, None)


class XMLEmitter(Emitter):
    def _to_xml(self, xml, data):
        if isinstance(data, list | tuple):
            for item in data:
                xml.startElement("resource", {})
                self._to_xml(xml, item)
                xml.endElement("resource")
        elif isinstance(data, dict):
            for key, value in data.items():
                xml.startElement(key, {})
                self._to_xml(xml, value)
                xml.endElement(key)
        else:
            xml.characters(smart_str(data))

    def render(self, request):
        stream = io.BytesIO()

        xml = SimplerXMLGenerator(stream, "utf-8")
        xml.startDocument()
        xml.startElement("response", {})

        self._to_xml(xml, self.construct())

        xml.endElement("response")
        xml.endDocument()

        return stream.getvalue()


Emitter.register("xml", XMLEmitter, "text/xml; charset=utf-8")
Mimer.register(lambda *a: None, ("text/xml",))


class JSONEmitter(Emitter):
    """
    JSON emitter, understands timestamps.
    """

    def render(self, request):
        cb = request.GET.get("callback", None)
        seria = json.dumps(
            self.construct(),
            cls=DjangoJSONEncoder,
            ensure_ascii=False,
            indent=4,
        )

        # Callback
        if cb and is_valid_jsonp_callback_value(cb):
            return f"{cb}({seria})"

        return seria


Emitter.register("json", JSONEmitter, "application/json; charset=utf-8")
Mimer.register(json.loads, ("application/json",))


class YAMLEmitter(Emitter):
    """
    YAML emitter, uses `safe_dump` to omit the
    specific types when outputting to non-Python.
    """

    def render(self, request):
        return yaml.safe_dump(self.construct())


Emitter.register("yaml", YAMLEmitter, "application/x-yaml; charset=utf-8")
Mimer.register(lambda s: dict(yaml.safe_load(s)), ("application/x-yaml",))


class PickleEmitter(Emitter):
    """
    Emitter that returns Python pickled.
    """

    def render(self, request):
        return pickle.dumps(self.construct())


Emitter.register("pickle", PickleEmitter, "application/python-pickle")

"""
WARNING: Accepting arbitrary pickled data is a huge security concern.
The unpickler has been disabled by default now, and if you want to use
it, please be aware of what implications it will have.

Read more: http://nadiana.com/python-pickle-insecure

Uncomment the line below to enable it. You're doing so at your own risk.
"""
# Mimer.register(pickle.loads, ('application/python-pickle',))


class DjangoEmitter(Emitter):
    """
    Emitter for the Django serialized format.
    """

    def render(self, request, format="xml"):
        if isinstance(self.data, HttpResponse):
            return self.data
        elif isinstance(self.data, int | str):
            response = self.data
        else:
            response = serializers.serialize(format, self.data, indent=True)

        return response


Emitter.register("django", DjangoEmitter, "text/xml; charset=utf-8")
