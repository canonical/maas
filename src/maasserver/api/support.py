# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Supporting infrastructure for Piston-based APIs in MAAS."""

__all__ = [
    "admin_method",
    "AnonymousOperationsHandler",
    "ModelCollectionOperationsHandler",
    "ModelOperationsHandler",
    "operation",
    "OperationsHandler",
]

from abc import ABCMeta, abstractproperty
from functools import wraps
import inspect
import re

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from piston3.authentication import NoAuthentication
from piston3.emitters import Emitter
from piston3.handler import AnonymousBaseHandler, BaseHandler, HandlerMetaClass
from piston3.resource import Resource
from piston3.utils import HttpStatusCode, rc

from maasserver.api.doc import get_api_description
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
    MAASBadDeprecation,
)
from maasserver.utils.orm import get_one
from provisioningserver.logger import LegacyLogger

log = LegacyLogger()


class OperationsResource(Resource):
    """A resource supporting operation dispatch.

    All requests are passed onto the handler's `dispatch` method. See
    :class:`OperationsHandler`.
    """

    crudmap = Resource.callmap
    callmap = dict.fromkeys(crudmap, "dispatch")

    @staticmethod
    def _use_emitter(result):
        """Override to force piston to the correct thing with Dango >=1.7."""
        # Always return False because we don't want Pison to do the wrong
        # thing with the content in HttpResponse objects. (Django 1.7 removed
        # the _base_content_is_iter attribute so there is no way to identify
        # the content inside of the response.) This means we never want Piston
        # to use its emitter on the contents inside of an HttpResponse.
        return False

    def __call__(self, request, *args, **kwargs):
        response = super().__call__(request, *args, **kwargs)
        response["X-MAAS-API-Hash"] = get_api_description()["hash"]
        return response

    def error_handler(self, e, request, meth, em_format):
        """
        Override piston's error_handler to fix bug #1228205 and generally
        do not hide exceptions.
        Also override Djangos default 404 handler to fix bug #1951229 and
        provide a more informative error message in the cli
        """
        if isinstance(e, Http404):
            return HttpResponse(str(e), content_type="text/plain", status=404)
        elif isinstance(e, HttpStatusCode):
            return e.response
        else:
            raise

    @property
    def is_authentication_attempted(self):
        """Will use of this resource attempt to authenticate the client?

        For example, `None`, ``[]``, and :class:`NoAuthentication` are all
        examples of authentication handlers that do *not* count.
        """
        return len(self.authentication) != 0 and not any(
            isinstance(auth, NoAuthentication) for auth in self.authentication
        )


class RestrictedResource(OperationsResource):
    """A resource that's restricted to active users."""

    def __init__(self, handler, *, authentication):
        """A value for `authentication` MUST be provided AND be meaningful.

        This prevents the situation where none of the following are restricted
        at all::

          handler = RestrictedResource(HandlerClass)
          handler = RestrictedResource(HandlerClass, authentication=None)
          handler = RestrictedResource(HandlerClass, authentication=[])

        """
        super().__init__(handler, authentication)
        if not self.is_authentication_attempted:
            raise AssertionError("Authentication must be attempted.")

    def authenticate(self, request, rm):
        actor, anonymous = super().authenticate(request, rm)
        if not anonymous and not request.user.is_active:
            raise PermissionDenied("User is not allowed access to this API.")
        else:
            return actor, anonymous


class AdminRestrictedResource(RestrictedResource):
    """A resource that's restricted to administrators."""

    def authenticate(self, request, rm):
        actor, anonymous = super().authenticate(request, rm)
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


def deprecated(use):
    """Decorator to note a method or class is deprecated on the API.

    :param use: Name of the method or class that should be used in place of this method
    """

    # TODO: Determine any other behaviours we might want from this decorator in future

    def update_method_docstring(func):
        doc = func.__doc__ if func.__doc__ else ""
        depr = f"This operation has been deprecated in favour of '{func_name(use)} {func_name(func.deprecated)}'"
        if "@description" in doc:
            description = doc.split("@description ")[1].split(".")[0]
            func.__doc = doc.replace(description, f"{description}. {depr}")
        else:
            func.__doc__ = f"{doc}\n{depr}."

    def update_class_docstring(cls):
        cls.__doc__ = f"{cls.__doc__}\nThe '{func_name(cls)}' endpoint has been deprecated in favour of '{func_name(use)}'."
        if "(deprecated)" not in cls.api_doc_section_name:
            cls.api_doc_section_name += " (deprecated)"

    def func_name(func):
        return re.sub(
            "[_ ]", "-", getattr(func, "api_doc_section_name", func.__name__)
        )

    def _decorator(func):
        if type(func) is not type(use):
            raise MAASBadDeprecation(
                f"{func_name(func)} is deprecated in favour of {func_name(use)}, but {type(use)} is not a valid replacement for {type(func)}"
            )
        func.deprecated = use
        # if an endpoint (class) was passed to the decorator, apply the decorator to all of it's methods too
        if isinstance(func, type):
            apply_to_methods(func)
            update_class_docstring(func)
        else:
            update_method_docstring(func)
        return func

    def apply_to_methods(cls):
        for name, method in inspect.getmembers(cls, inspect.isfunction):
            new_method = getattr(use, name, None)
            if new_method:
                method.deprecated = new_method
                update_method_docstring(method)

    return _decorator


METHOD_RESERVED_ADMIN = "This method is reserved for admin users."


def admin_method(func):
    """Decorator to protect a method from non-admin users.

    If a non-admin tries to call a method decorated with this decorator,
    they will get an HTTP "forbidden" error and a message saying the
    operation is accessible only to administrators.
    """

    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied(METHOD_RESERVED_ADMIN)
        else:
            return func(self, request, *args, **kwargs)

    return wrapper


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
        cls = super().__new__(metaclass, name, bases, namespace)

        # Create a signature:function mapping for CRUD operations.
        crud = {
            (http_method, None): getattr(cls, method)
            for http_method, method in list(OperationsResource.crudmap.items())
            if getattr(cls, method, None) is not None
        }

        # Create a signature:function mapping for non-CRUD operations.
        operations = {
            attribute.export: attribute
            for attribute in list(vars(cls).values())
            if getattr(attribute, "export", None) is not None
        }

        # Create the exports mapping.
        exports = {}

        # Add parent classes' exports if they still correspond to a valid
        # method on the class we're considering. This allows subclasses to
        # remove methods by defining an attribute of the same name as None.
        for base in bases:
            for key, value in vars(base).items():
                export = getattr(value, "export", None)
                if export is not None:
                    new_func = getattr(cls, key, None)
                    if new_func is not None:
                        exports[export] = new_func

        # Export custom operations.
        exports.update(operations)

        # Check that no CRUD methods have been marked as operations (i.e.
        # those that are used via op=name). This causes (unconfirmed) weird
        # behaviour within Piston3 and/or Django, and is plain confusing
        # anyway, so forbid it.
        methods_exported = {method for http_method, method in exports}
        for http_method, method in OperationsResource.crudmap.items():
            if method in methods_exported:
                raise AssertionError(
                    "A CRUD operation (%s/%s) has been registered as an "
                    "operation on %s." % (http_method, method, name)
                )

        # Export CRUD methods.
        exports.update(crud)

        # Update the class.
        cls.exports = exports
        cls.allowed_methods = frozenset(
            http_method for http_method, name in exports
        )

        # Flags used later.
        has_fields = cls.fields is not BaseHandler.fields
        has_resource_uri = hasattr(cls, "resource_uri")
        is_internal_only = cls.__module__ in {__name__, "metadataserver.api"}

        # Reject handlers which omit fields required for self-referential
        # URIs. See bug 1643552. We ignore handlers that don't define `fields`
        # because we assume they are doing custom object rendering and we have
        # no way to check here for compliance.
        if has_fields and has_resource_uri:
            _, uri_params, *_ = cls.resource_uri()
            missing = set(uri_params).difference(cls.fields)
            if len(missing) != 0:
                raise OperationsHandlerMisconfigured(
                    "{handler.__module__}.{handler.__name__} does not render "
                    "all fields required to construct a self-referential URI. "
                    "Fields missing: {missing}.".format(
                        handler=cls, missing=" ".join(sorted(missing))
                    )
                )

        # Piston uses `resource_uri` even for handlers without models in order
        # to generate documentation. We ignore those modules we consider "for
        # internal use only" since we do not intend to generate documentation
        # for these.
        if (
            not has_resource_uri
            and not is_internal_only
            and not cls.is_anonymous
        ):
            log.warn(
                "{handler.__module__}.{handler.__name__} does not have "
                "`resource_uri`. This means it may be omitted from generated "
                "documentation. Please investigate.",
                handler=cls,
            )

        return cls


class OperationsHandlerMisconfigured(Exception):
    """Handler has been misconfigured; see the error message for details."""


RE_OPER = re.compile(r"^.+/op-(?P<op>[^/]+)$")


class OperationsHandlerMixin:
    """Handler mixin for operations dispatch.

    This enabled dispatch to custom functions that piggyback on HTTP methods
    that ordinarily, in Piston, are used for CRUD operations.

    This must be used in cooperation with :class:`OperationsResource` and
    :class:`OperationsHandlerType`.
    """

    # CSRF protection is on by default.  Only pure 0-legged oauth API requests
    # don't go through the CSRF machinery (see
    # middleware.CSRFHelperMiddleware).
    # This is a field used by piston to decide whether or not CSRF protection
    # should be performed.
    csrf_exempt = False

    # Populated by OperationsHandlerType.
    exports = None

    # Specified by subclasses.
    anonymous = None

    def dispatch(self, request, *args, **kwargs):
        op = request.GET.get("op") or request.POST.get("op")
        if op is None:
            match = RE_OPER.match(request.path)
            op = match.group("op") if match else None
        signature = request.method.upper(), op
        function = self.exports.get(signature)
        if function is None:
            raise MAASAPIBadRequest(
                "Unrecognised signature: method=%s op=%s" % signature
            )
        else:
            return function(self, request, *args, **kwargs)

    @classmethod
    def decorate(cls, func):
        """Decorate all exported operations with the given function.

        Exports are stored in a class attribute. Calling this function
        replaces that attribute, with all the exported functions decorated
        with `decorate`. This can be called multiple times to add additional
        layers of decoration.

        :param func: A single-argument callable.
        """
        cls.exports = {
            name: func(export) for name, export in cls.exports.items()
        }
        # Now also decorate the anonymous handler, if present.
        if cls.anonymous is not None and bool(cls.anonymous):
            if issubclass(cls.anonymous, OperationsHandlerMixin):
                cls.anonymous.decorate(func)


class OperationsHandler(
    OperationsHandlerMixin, BaseHandler, metaclass=OperationsHandlerType
):
    """Base handler that supports operation dispatch."""


class AnonymousOperationsHandler(
    OperationsHandlerMixin,
    AnonymousBaseHandler,
    metaclass=OperationsHandlerType,
):
    """Anonymous base handler that supports operation dispatch."""


def method_fields_reserved_fields_patch(self, handler, fields):
    """Return the field callables that map to a handler.

    Piston by default does not allow the ability to use names of fields
    that are the same as other class attributes.

    This overrides this ability and prefixes any `RESERVED_FIELDS` with "_"
    to allow handlers to still use that field.

    E.g. "model" classmethod on the `BlockDeviceHandler`.
    """
    if not handler:
        return {}
    ret = dict()
    for field in fields:
        field_method = field
        if field in Emitter.RESERVED_FIELDS:
            field_method = "_%s" % field_method
        t = getattr(handler, str(field_method), None)
        if t and callable(t):
            ret[field] = t
    return ret


Emitter.method_fields = method_fields_reserved_fields_patch

# only keep the JSON emitter as it's the only format we support
for name in list(Emitter.EMITTERS):
    if name == "json":
        continue
    Emitter.unregister(name)


class ModelOperationsHandlerType(OperationsHandlerType, ABCMeta):
    """Metaclass for ModelOperationsHandler"""


class ModelOperationsHandler(
    OperationsHandler, metaclass=ModelOperationsHandlerType
):
    """Manage API access for a model.

    By default, the id is used as unique identifier to get instances. It can be
    changed by setting `id_field` to the desired model field.

    """

    @abstractproperty
    def model(self):
        """Model class for database operations."""

    id_field = "id"  # can be overridden by subclasses

    @abstractproperty
    def model_form(self):
        """A Form class used to validate data for the Model."""

    @abstractproperty
    def handler_url_name(cls):
        """Name of the handler for the API."""

    @classmethod
    def resource_uri(cls, instance=None):
        if instance:
            id_value = getattr(instance, cls.id_field)
        else:
            id_value = cls.id_field
        return (cls.handler_url_name, [id_value])

    create = None  # create is handled by the collection class.

    def read(self, request, **kwargs):
        """GET request.  Return a single model instance."""
        instance = self._get_instance_or_404(**kwargs)
        permission_read = getattr(self, "permission_read", None)
        if permission_read is not None:
            if not request.user.has_perm(permission_read, instance):
                raise PermissionDenied()
        return instance

    @admin_method
    def update(self, request, **kwargs):
        """PUT request.  Update a model instance.

        If the instance is not found, return 404.
        """
        instance = self._get_instance_or_404(**kwargs)
        form = self.model_form(instance=instance, data=request.data)
        if hasattr(form, "use_perms") and form.use_perms():
            if not form.has_perm(request.user):
                raise PermissionDenied()
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        return form.save()

    @admin_method
    def delete(self, request, **kwargs):
        """DELETE request.  Delete a model instance."""
        filters = {self.id_field: kwargs[self.id_field]}
        instance = get_one(self.model.objects.filter(**filters))
        permission_delete = getattr(self, "permission_delete", None)
        if permission_delete is not None:
            if not request.user.has_perm(permission_delete, instance):
                raise PermissionDenied()
        if instance:
            instance.delete()
        return rc.DELETED

    def _get_instance_or_404(self, **kwargs):
        return get_object_or_404(self.model, **kwargs)


class ModelCollectionOperationsHandler(
    OperationsHandler, metaclass=ModelOperationsHandlerType
):
    """Manage API access for a model collection."""

    @abstractproperty
    def model_manager(self):
        """Manager class for database operations."""

    @abstractproperty
    def model_form(self):
        """A Form class used to validate data for the Model."""

    @abstractproperty
    def handler_url_name(cls):
        """Name of the handler for the API."""

    # Model field to use for collection ordering.
    order_field = "name"

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return (cls.handler_url_name, [])

    def create(self, request):
        """POST request.  Create a new instance of the model."""
        form = self.model_form(request.data)
        if hasattr(form, "use_perms") and form.use_perms():
            if not form.has_perm(request.user):
                raise PermissionDenied()
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def read(self, request):
        """GET request.  List all model instances ordered by name."""
        return self.model_manager.all().order_by(self.order_field)

    update = delete = None
