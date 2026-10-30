# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Request-local model serialization for read-only collection responses."""

import inspect

from django.db.models import Model
from django.db.models.query import QuerySet, RawQuerySet
from django.urls import NoReverseMatch
from piston3 import emitters


class ModelCachingJSONEmitter(emitters.JSONEmitter):
    """Reuse handler methods and model representations within a response."""

    def construct(self):
        if not (
            getattr(self.handler, "cache_model_serialization", False)
            and isinstance(self.data, (list, tuple, QuerySet, RawQuerySet))
        ):
            return super().construct()
        self._model_cache = {}
        self._method_cache = {}
        self._handler_cache = {}
        self._active_models = []
        self._active_containers = set()
        try:
            return self._value(self.data, self.fields)
        finally:
            self._model_cache.clear()
            self._method_cache.clear()
            self._handler_cache.clear()
            self._active_models.clear()
            self._active_containers.clear()

    def _value(self, value, fields=None):
        if value is None or type(value) in (str, int, float, bool):
            return value
        if isinstance(value, Model):
            if value in self._active_models:
                raise RuntimeError(
                    "Circular reference detected while emitting response"
                )
            self._active_models.append(value)
            try:
                return self._model(value, fields)
            finally:
                self._active_models.pop()
        if isinstance(value, (dict, list, tuple, set, QuerySet, RawQuerySet)):
            identity = id(value)
            if identity in self._active_containers:
                raise RuntimeError(
                    "Circular reference detected while emitting response"
                )
            self._active_containers.add(identity)
            try:
                if isinstance(value, dict):
                    return {
                        key: self._value(item, fields)
                        for key, item in value.items()
                    }
                return [self._value(item, fields) for item in value]
            finally:
                self._active_containers.remove(identity)
        # Keep Piston's conversions for dates, decimals, bytes, emittable
        # objects and HTTP responses rather than duplicating those rules.
        return emitters.Emitter(
            value, self.typemapper, self.handler, fields, self.anonymous
        ).construct()

    def _related(self, manager, fields=None):
        return [self._model(model, fields) for model in manager.all()]

    def _model(self, model, fields):
        model_type = type(model)
        if model_type not in self._handler_cache:
            self._handler_cache[model_type] = self.in_typemapper(
                model_type, self.anonymous
            )
        handler = self._handler_cache[model_type]
        fields = fields or getattr(handler, "fields", None)
        if not fields:
            # Implicit model fields and exclusions remain Piston's concern.
            return emitters.Emitter(
                model, self.typemapper, self.handler, fields, self.anonymous
            ).construct()

        fields = frozenset(fields)
        key = id(model), fields
        if key in self._model_cache:
            return self._model_cache[key][1]
        method_key = handler, fields
        if method_key not in self._method_cache:
            self._method_cache[method_key] = self.method_fields(
                handler, fields
            )
        methods = self._method_cache[method_key]
        result = {}
        for field in fields:
            if isinstance(field, (list, tuple)):
                name, nested_fields = field
                value = getattr(model, name, None)
                if value:
                    # Piston permits bounded back-references through explicit
                    # related projections; only normal values enter its stack.
                    if hasattr(value, "all"):
                        result[name] = self._related(value, nested_fields)
                    elif callable(value):
                        if len(inspect.signature(value).parameters) == 1:
                            result[name] = self._value(value(), nested_fields)
                    else:
                        result[name] = self._model(value, nested_fields)
            elif field in methods:
                result[field] = self._value(methods[field](model))
            else:
                try:
                    value = getattr(model, field)
                except AttributeError:
                    method = getattr(handler or self.handler, field, None)
                    if method:
                        result[field] = self._value(method(model))
                else:
                    if hasattr(value, "all"):
                        result[field] = self._related(value)
                        continue
                    if callable(value):
                        required = [
                            parameter
                            for parameter in inspect.signature(
                                value
                            ).parameters.values()
                            if parameter.default is inspect.Parameter.empty
                        ]
                        if len(required) > 1:
                            continue
                        value = value()
                    result[field] = self._value(value)
        if handler and hasattr(handler, "resource_uri"):
            url, args = handler.resource_uri(model)
            try:
                result["resource_uri"] = emitters.reverser(url, args=args)
            except NoReverseMatch:
                pass
        if hasattr(model, "get_api_url") and "resource_uri" not in result:
            try:
                result["resource_uri"] = model.get_api_url()
            except Exception:
                pass
        # Retain the instance: a later temporary model must not reuse its
        # identity and accidentally receive this representation.
        self._model_cache[key] = model, result
        return result
