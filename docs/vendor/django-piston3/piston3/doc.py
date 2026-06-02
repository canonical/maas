import inspect

from django.core.exceptions import ViewDoesNotExist
from django.shortcuts import render
from django.urls import (
    get_callable,
    get_resolver,
    get_script_prefix,
)

from . import handler
from .handler import handler_tracker


def generate_doc(handler_cls):
    """
    Returns a `HandlerDocumentation` object
    for the given handler. Use this to generate
    documentation for your API.
    """
    if isinstance(type(handler_cls), handler.HandlerMetaClass):
        raise ValueError(f"Give me handler, not {type(handler_cls)}")

    return HandlerDocumentation(handler_cls)


class HandlerMethod:
    def __init__(self, method, stale=False):
        self.method = method
        self.stale = stale

    def iter_args(self):
        signature = inspect.signature(self.method)
        for name, param in signature.parameters.items():
            if name in ("self", "request", "form"):
                continue

            if param.default is inspect.Parameter.empty:
                yield (name, None)
            else:
                yield (name, str(param.default))

    @property
    def signature(self, parse_optional=True):
        spec = ""

        for argn, argdef in self.iter_args():
            spec += argn

            if argdef:
                spec += f"={argdef}"

            spec += ", "

        spec = spec.rstrip(", ")

        if parse_optional:
            return spec.replace("=None", "=<optional>")

        return spec

    @property
    def doc(self):
        return inspect.getdoc(self.method)

    @property
    def name(self):
        return self.method.__name__

    @property
    def http_name(self):
        if self.name == "read":
            return "GET"
        elif self.name == "create":
            return "POST"
        elif self.name == "delete":
            return "DELETE"
        elif self.name == "update":
            return "PUT"

    def __repr__(self):
        return f"<Method: {self.name}>"


class HandlerDocumentation:
    def __init__(self, handler):
        self.handler = handler

    def get_methods(self, include_default=False):
        for method in "read create update delete".split():
            met = getattr(self.handler, method, None)

            if not met:
                continue

            stale = inspect.getmodule(met.__func__) is not inspect.getmodule(
                self.handler
            )

            if not self.handler.is_anonymous:
                if met and (not stale or include_default):
                    yield HandlerMethod(met, stale)
            else:
                if (
                    not stale
                    or met.__name__ == "read"
                    and "GET" in self.allowed_methods
                ):
                    yield HandlerMethod(met, stale)

    def get_all_methods(self):
        return self.get_methods(include_default=True)

    @property
    def is_anonymous(self):
        return self.handler.is_anonymous

    def get_model(self):
        return getattr(self, "model", None)

    @property
    def has_anonymous(self):
        return self.handler.anonymous

    @property
    def anonymous(self):
        if self.has_anonymous:
            return HandlerDocumentation(self.handler.anonymous)

    @property
    def doc(self):
        return self.handler.__doc__

    @property
    def name(self):
        return self.handler.__name__

    @property
    def allowed_methods(self):
        return self.handler.allowed_methods

    def get_resource_uri_template(self):
        """
        URI template processor.

        See http://bitworking.org/projects/URI-Templates/
        """

        def _convert(template, params=[]):
            """URI template converter"""
            paths = template % dict([p, f"{{{p}}}"] for p in params)
            return f"{get_script_prefix()}{paths}"

        try:
            resource_uri = self.handler.resource_uri()

            components = [None, [], {}]

            for i, value in enumerate(resource_uri):
                components[i] = value

            lookup_view, args, kwargs = components
            try:
                lookup_view = get_callable(lookup_view)
            except (ImportError, ViewDoesNotExist):
                # Django 1.11 drops the can_fail argument on get_callable,
                # so we ignore failures here..
                pass

            possibilities = get_resolver(None).reverse_dict.getlist(
                lookup_view
            )

            for possibility in possibilities:
                for result, params in possibility[0]:
                    if args:
                        if len(args) != len(params):
                            continue
                        return _convert(result, params)
                    else:
                        if set(kwargs.keys()) != set(params):
                            continue
                        return _convert(result, params)
        except Exception:
            return None

    resource_uri_template = property(get_resource_uri_template)

    def __repr__(self):
        return f'<Documentation for "{self.name}">'


def documentation_view(request):
    """
    Generic documentation view. Generates documentation
    from the handlers you've defined.
    """
    docs = []

    for h in handler_tracker:
        docs.append(generate_doc(h))

    docs.sort(lambda doc: doc.name.replace("Anonymous", ""))

    return render(
        request,
        "documentation.html",
        {"docs": docs},
    )
