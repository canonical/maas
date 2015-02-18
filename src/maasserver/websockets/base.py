# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The base class that all handlers must extend."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "HandlerError",
    "HandlerPKError",
    "HandlerValidationError",
    "Handler",
    ]


from django.core.exceptions import ValidationError
from django.utils.encoding import is_protected_type
from maasserver.utils.async import transactional
from maasserver.utils.forms import get_QueryDict
from provisioningserver.utils.twisted import synchronous


class HandlerError(Exception):
    """Generic exception a handler can raise."""


class HandlerNoSuchMethodError(HandlerError):
    """Raised when an handler doesn't have that method."""


class HandlerPKError(HandlerError):
    """Raised when object is missing its primary key."""


class HandlerValidationError(HandlerError, ValidationError):
    """Raised when object fails to validate on create or update."""


class HandlerDoesNotExistError(HandlerError):
    """Raised when an object by its `pk` doesn't exist."""


class HandlerOptions(object):
    """Configuraton class for `Handler`.

    Provides the needed defaults to the internal `Meta` class used on
    the handler.
    """
    abstract = False
    allowed_methods = ['list', 'get', 'create', 'update', 'delete']
    handler_name = None
    object_class = None
    queryset = None
    pk = 'id'
    fields = None
    exclude = None
    list_fields = None
    list_exclude = None
    non_changeable = None
    form = None
    listen_channels = []

    def __new__(cls, meta=None):
        overrides = {}

        # Meta class will override the defaults based on the values it
        # already has set.
        if meta:
            for override_name in dir(meta):
                # Skip over internal field names.
                if not override_name.startswith('_'):
                    overrides[override_name] = getattr(meta, override_name)

        # Construct the new object with the overrides from meta.
        return object.__new__(
            type(b'HandlerOptions', (cls,), overrides))


class HandlerMetaclass(type):
    """Sets up the _meta field on the created class."""

    def __new__(cls, name, bases, attrs):
        # Construct the class with the _meta field.
        new_class = super(
            HandlerMetaclass, cls).__new__(cls, name, bases, attrs)
        new_class._meta = HandlerOptions(getattr(new_class, 'Meta', None))

        # Setup the handlers name based on the naming of the class.
        if not getattr(new_class._meta, 'handler_name', None):
            class_name = new_class.__name__
            name_bits = [bit for bit in class_name.split('Handler') if bit]
            handler_name = ''.join(name_bits).lower()
            new_class._meta.handler_name = handler_name

        # Setup the object_class if the queryset is provided.
        if new_class._meta.queryset is not None:
            new_class._meta.object_class = new_class._meta.queryset.model

        # Copy the fields and exclude to list_fields and list_exclude
        # if empty.
        if new_class._meta.list_fields is None:
            new_class._meta.list_fields = new_class._meta.fields
        if new_class._meta.list_exclude is None:
            new_class._meta.list_exclude = new_class._meta.exclude

        return new_class


class Handler:
    """Base handler for all handlers in the WebSocket protocol.

    Each handler should extend this class to get the basic implementation of
    exposing a collection over the WebSocket protocol. The classes that extend
    this class must be present in `maasserver.websockets.handlers` for it to
    be exposed.

    Example:

        class SampleHandler(Handler):

            class Meta:
                queryset = Sample.objects.all()

    """

    __metaclass__ = HandlerMetaclass

    def __init__(self, user):
        self.user = user

    def full_dehydrate(self, obj, for_list=False):
        """Convert the given object into a dictionary.

        :param for_list: True when the object is being converted to belong
            in a list.
        """
        if for_list:
            allowed_fields = self._meta.list_fields
            exclude_fields = self._meta.list_exclude
        else:
            allowed_fields = self._meta.fields
            exclude_fields = self._meta.exclude

        data = {}
        for field in self._meta.object_class._meta.fields:
            # Convert the field name to unicode as some are stored in bytes.
            field_name = unicode(field.name)

            # Skip fields that are not allowed.
            if allowed_fields is not None and field_name not in allowed_fields:
                continue
            if exclude_fields is not None and field_name in exclude_fields:
                continue

            # Get the value from the field and set it in data. The value
            # will pass throught the dehydrate method if present.
            field_obj = getattr(obj, field_name)
            dehydrate_method = getattr(
                self, "dehydrate_%s" % field_name, None)
            if dehydrate_method is not None:
                data[field_name] = dehydrate_method(field_obj)
            else:
                value = field._get_val_from_obj(obj)
                if is_protected_type(value):
                    data[field_name] = value
                else:
                    data[field_name] = field.value_to_string(obj)

        # Return the data after the final dehydrate.
        return self.dehydrate(obj, data, for_list=for_list)

    def dehydrate(self, obj, data, for_list=False):
        """Add any extra info to the `data` before finalizing the final object.

        :param obj: object being dehydrated.
        :param data: dictionary to place extra info.
        :param for_list: True when the object is being converted to belong
            in a list.
        """
        return data

    def full_hydrate(self, obj, data):
        """Convert the given dictionary to a object."""
        allowed_fields = self._meta.fields
        exclude_fields = self._meta.exclude
        non_changeable_fields = self._meta.non_changeable

        for field in self._meta.object_class._meta.fields:
            field_name = field.name

            # Skip fields that are not allowed.
            if field_name == self._meta.pk:
                continue
            if allowed_fields is not None and field_name not in allowed_fields:
                continue
            if exclude_fields is not None and field_name in exclude_fields:
                continue
            if (non_changeable_fields is not None and
                    field_name in non_changeable_fields):
                continue

            # Update the field if its in the provided data. Passing the value
            # through its hydrate method if present.
            if field_name in data:
                value = data[field_name]
                hydrate_method = getattr(self, "hydrate_%s" % field_name, None)
                if hydrate_method is not None:
                    value = hydrate_method(value)
                setattr(obj, field_name, value)

        # Return the hydrated object once its done the final hydrate.
        return self.hydrate(obj, data)

    def hydrate(self, obj, data):
        """Add any extra info to the `obj` before finalizing the finale object.

        :param obj: obj being hydrated.
        :param data: dictionary to use to set object.
        """
        return obj

    def get_object(self, params):
        """Get object by using the `pk` in `params`."""
        if self._meta.pk not in params:
            raise HandlerPKError("Missing %s in params" % self._meta.pk)
        pk = params[self._meta.pk]
        try:
            obj = self._meta.object_class.objects.get(**{
                self._meta.pk: pk,
                })
        except self._meta.object_class.DoesNotExist:
            raise HandlerDoesNotExistError(pk)
        return obj

    def get_queryset(self):
        """Return `QuerySet` used by this handler.

        Override if you need to modify the queryset based on the current user.
        """
        return self._meta.queryset

    def get_form_class(self, action):
        """Return the form class used for `action`.

        Override if you need to provide a form based on the current user.
        """
        return self._meta.form

    def preprocess_form(self, action, params):
        """Process the `params` to before passing the data to the form.

        Default implementation just converts `params` to a `QueryDict`.
        """
        return get_QueryDict(params)

    @synchronous
    @transactional
    def execute(self, method, params):
        """Execute the given method on the handler.

        Checks to make sure the method is valid and allowed perform executing
        the method.
        """
        if method not in self._meta.allowed_methods:
            raise HandlerNoSuchMethodError(method)
        m = getattr(self, method, None)
        if m is None:
            raise HandlerNoSuchMethodError(method)
        return m(params)

    def list(self, params):
        """List objects.

        :param offset: Offset into the queryset to return.
        :param limit: Maximum number of objects to return.
        """
        queryset = self.get_queryset()
        queryset = queryset.order_by(self._meta.pk)
        if "start" in params:
            queryset = queryset.filter(**{
                "%s__gt" % self._meta.pk: params["start"]
                })
        if "limit" in params:
            queryset = queryset[:params["limit"]]
        return [
            self.full_dehydrate(obj, for_list=True)
            for obj in queryset
            ]

    def get(self, params):
        """Get object.

        :param pk: Object with primary key to return.
        """
        return self.full_dehydrate(self.get_object(params))

    def create(self, params):
        """Create the object from data."""
        # Create by using form
        form_class = self.get_form_class("create")
        if form_class is not None:
            data = self.preprocess_form("create", params)
            form = form_class(data=data)
            if form.is_valid():
                try:
                    obj = form.save()
                except ValidationError as e:
                    raise HandlerValidationError(e.error_dict)
                return self.full_dehydrate(obj)
            else:
                raise HandlerValidationError(form.errors)

        # Create by updating the fields on the object.
        obj = self._meta.object_class()
        obj = self.full_hydrate(obj, params)
        obj.save()
        return self.full_dehydrate(obj)

    def update(self, params):
        """Update the object."""
        obj = self.get_object(params)

        # Update by using form.
        form_class = self.get_form_class("update")
        if form_class is not None:
            data = self.preprocess_form("update", params)
            form = form_class(data=data, instance=obj)
            if form.is_valid():
                try:
                    obj = form.save()
                except ValidationError as e:
                    raise HandlerValidationError(e.error_dict)
                return self.full_dehydrate(obj)
            else:
                raise HandlerValidationError(form.errors)

        # Update by updating the fields on the object.
        obj = self.full_hydrate(obj, params)
        obj.save()
        return self.full_dehydrate(obj)

    def delete(self, params):
        """Delete the object."""
        obj = self.get_object(params)
        obj.delete()

    def on_listen(self, channel, action, pk):
        """Called by the protocol when a channel notification occurs.

        Do not override this method instead override `listen`.
        """
        obj = self.listen(channel, action, pk)
        if obj is None:
            return None
        if action == "delete":
            return (self._meta.handler_name, obj)
        else:
            return (
                self._meta.handler_name,
                self.full_dehydrate(obj, for_list=False),
                )

    def listen(self, channel, action, pk):
        """Called when the handler listens for events on channels with
        `Meta.listen_channels`.

        :param channel: Channel event occured on.
        :param action: Action that caused this event.
        :param pk: Id of the object.
        """
        if action == "delete":
            return pk
        return self.get_object({
            self._meta.pk: pk
            })
