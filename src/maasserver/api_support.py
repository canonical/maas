# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Supporting infrastructure for Piston-based APIs in MAAS."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'AnonymousOperationsHandler',
    'operation',
    'OperationsHandler',
    ]

from django.core.exceptions import PermissionDenied
from django.http import (
    Http404,
    HttpResponseBadRequest,
    )
from piston.handler import (
    AnonymousBaseHandler,
    BaseHandler,
    HandlerMetaClass,
    )
from piston.resource import Resource
from piston.utils import (
    HttpStatusCode,
    rc,
    )


class OperationsResource(Resource):
    """A resource supporting operation dispatch.

    All requests are passed onto the handler's `dispatch` method. See
    :class:`OperationsHandler`.
    """

    crudmap = Resource.callmap
    callmap = dict.fromkeys(crudmap, "dispatch")

    def error_handler(self, e, request, meth, em_format):
        """
        Override piston's error_handler to fix bug #1228205 and generally
        do not hide exceptions.
        """
        if isinstance(e, Http404):
            return rc.NOT_FOUND
        elif isinstance(e, HttpStatusCode):
            return e.response
        else:
            raise


class RestrictedResource(OperationsResource):
    """A resource that's restricted to active users."""

    def authenticate(self, request, rm):
        actor, anonymous = super(
            RestrictedResource, self).authenticate(request, rm)
        if not anonymous and not request.user.is_active:
            raise PermissionDenied("User is not allowed access to this API.")
        else:
            return actor, anonymous


class AdminRestrictedResource(RestrictedResource):
    """A resource that's restricted to administrators."""

    def authenticate(self, request, rm):
        actor, anonymous = super(
            AdminRestrictedResource, self).authenticate(request, rm)
        if anonymous or not request.user.is_superuser:
            raise PermissionDenied("User is not allowed access to this API.")
        else:
            return actor, anonymous


def operation(idempotent, exported_as=None):
    """Decorator to make a method available on the API.

    :param idempotent: If this operation is idempotent. Idempotent operations
        are made available via HTTP GET, non-idempotent operations via HTTP
        POST.
    :param exported_as: Optional operation name; defaults to the name of the
        exported method.
    """
    method = "GET" if idempotent else "POST"

    def _decorator(func):
        if exported_as is None:
            func.export = method, func.__name__
        else:
            func.export = method, exported_as
        return func

    return _decorator


class OperationsHandlerType(HandlerMetaClass):
    """Type for handlers that dispatch operations.

    Collects all the exported operations, CRUD and custom, into the class's
    `exports` attribute. This is a signature:function mapping, where signature
    is an (http-method, operation-name) tuple. If operation-name is None, it's
    a CRUD method.

    The `allowed_methods` attribute is calculated as the union of all HTTP
    methods required for the exported CRUD and custom operations.
    """

    def __new__(metaclass, name, bases, namespace):
        cls = super(OperationsHandlerType, metaclass).__new__(
            metaclass, name, bases, namespace)

        # Create a signature:function mapping for CRUD operations.
        crud = {
            (http_method, None): getattr(cls, method)
            for http_method, method in OperationsResource.crudmap.items()
            if getattr(cls, method, None) is not None
            }

        # Create a signature:function mapping for non-CRUD operations.
        operations = {
            attribute.export: attribute
            for attribute in vars(cls).values()
            if getattr(attribute, "export", None) is not None
            }

        # Create the exports mapping.
        exports = {}
        exports.update(crud)
        exports.update(operations)

        # Update the class.
        cls.exports = exports
        cls.allowed_methods = frozenset(
            http_method for http_method, name in exports)

        return cls


class OperationsHandlerMixin:
    """Handler mixin for operations dispatch.

    This enabled dispatch to custom functions that piggyback on HTTP methods
    that ordinarily, in Piston, are used for CRUD operations.

    This must be used in cooperation with :class:`OperationsResource` and
    :class:`OperationsHandlerType`.
    """

    def dispatch(self, request, *args, **kwargs):
        signature = request.method.upper(), request.REQUEST.get("op")
        function = self.exports.get(signature)
        if function is None:
            return HttpResponseBadRequest(
                "Unrecognised signature: %s %s" % signature)
        else:
            return function(self, request, *args, **kwargs)


class OperationsHandler(
        OperationsHandlerMixin, BaseHandler):
    """Base handler that supports operation dispatch."""

    __metaclass__ = OperationsHandlerType


class AnonymousOperationsHandler(
        OperationsHandlerMixin, AnonymousBaseHandler):
    """Anonymous base handler that supports operation dispatch."""

    __metaclass__ = OperationsHandlerType
