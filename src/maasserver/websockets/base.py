# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The base class that all handlers must extend."""

__all__ = [
    "HandlerError",
    "HandlerPKError",
    "HandlerValidationError",
    "Handler",
]

import asyncio
from functools import reduce, wraps
from operator import attrgetter

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Model, Q
from django.utils.encoding import is_protected_type
from twisted.internet.defer import ensureDeferred
from twisted.internet.threads import deferToThread

from maasapiserver.client import APIServerClient
from maasserver import concurrency
from maasserver.permissions import NodePermission
from maasserver.prometheus.middleware import wrap_query_counter_cursor
from maasserver.rbac import rbac
from maasserver.utils.forms import get_QueryDict
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.certificates import Certificate
from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.utils.twisted import asynchronous, IAsynchronous

DATETIME_FORMAT = "%a, %d %b. %Y %H:%M:%S"


def dehydrate_datetime(datetime):
    """Convert the `datetime` to string with `DATETIME_FORMAT`."""
    if datetime is None:
        return ""
    else:
        return datetime.strftime(DATETIME_FORMAT)


def dehydrate_certificate(cert: Certificate):
    """Return a dict with metadata for a Certificate."""
    return {
        "CN": cert.cn(),
        "expiration": dehydrate_datetime(cert.expiration()),
        "fingerprint": cert.cert_hash(),
    }


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


class HandlerPermissionError(HandlerError):
    """Raised when permission is denied for the user of a given action."""

    def __init__(self):
        super().__init__("Permission denied")


class HandlerOptions:
    """Configuraton class for `Handler`.

    Provides the needed defaults to the internal `Meta` class used on
    the handler.
    """

    abstract = False
    allowed_methods = [
        "list",
        "get",
        "create",
        "update",
        "delete",
        "set_active",
        "unsubscribe",
    ]
    handler_name = None
    object_class = None
    queryset = None
    list_queryset = None
    use_sqlalchemy_list = None
    pk = "id"
    bulk_pk = "ids"
    pk_type = int
    fields = None
    exclude = None
    list_fields = None
    list_exclude = None
    non_changeable = None
    form = None
    form_requires_request = True
    listen_channels = []
    batch_key = "id"
    create_permission = None
    view_permission = None
    edit_permission = None
    delete_permission = None
    use_paginated_list = False
    dft_page_size = 100
    methods_using_apiserver = []

    def __new__(cls, meta=None):
        overrides = {}

        # Meta class will override the defaults based on the values it
        # already has set.
        if meta:
            for override_name in dir(meta):
                # Skip over internal field names.
                if not override_name.startswith("_"):
                    overrides[override_name] = getattr(meta, override_name)

        # Construct the new object with the overrides from meta.
        return object.__new__(type("HandlerOptions", (cls,), overrides))


class HandlerMetaclass(type):
    """Sets up the _meta field on the created class."""

    def __new__(cls, name, bases, attrs):
        # Construct the class with the _meta field.
        new_class = super().__new__(cls, name, bases, attrs)
        new_class._meta = HandlerOptions(getattr(new_class, "Meta", None))

        # Setup the handlers name based on the naming of the class.
        if not getattr(new_class._meta, "handler_name", None):
            class_name = new_class.__name__
            name_bits = [bit for bit in class_name.split("Handler") if bit]
            handler_name = "".join(name_bits).lower()
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


def _get_call_latency_metrics_label(args, *_):
    handler, method_name, *_ = args
    return {"call": f"{handler._meta.handler_name}.{method_name}"}


class Handler(metaclass=HandlerMetaclass):
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

    def __init__(self, user, cache, request, session_id=""):
        self.user = user
        self.cache = cache
        self.request = request
        # Holds a set of all pks that the client has loaded and has on their
        # end of the connection. This is used to inform the client of the
        # correct notifications based on what items the client has.
        if "loaded_pks" not in self.cache:
            self.cache["loaded_pks"] = set()
        self.api_client = APIServerClient(session_id)

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
            field_name = str(field.name)

            # Skip fields that are not allowed.
            if allowed_fields is not None and field_name not in allowed_fields:
                continue
            if exclude_fields is not None and field_name in exclude_fields:
                continue

            # Get the value from the field and set it in data. The value
            # will pass through the dehydrate method if present.
            field_obj = getattr(obj, field_name)
            dehydrate_method = getattr(self, "dehydrate_%s" % field_name, None)
            if dehydrate_method is not None:
                data[field_name] = dehydrate_method(field_obj)
            else:
                value = field.value_from_object(obj)
                if is_protected_type(value) or isinstance(value, dict):
                    data[field_name] = value
                elif isinstance(field, ArrayField):
                    data[field_name] = field.to_python(value)
                else:
                    data[field_name] = field.value_to_string(obj)

        # Add permissions that can be performed on this object.
        data = self._add_permissions(obj, data)

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

    def _is_foreign_key_for(self, field_name, obj, value):
        """Given the specified field name for the specified object, returns
        True if the specified value is a foreign key; otherwise returns False.
        """
        if isinstance(obj, Model):
            field_type = obj._meta.get_field(field_name).get_internal_type()
            if field_type == "ForeignKey" and not isinstance(value, Model):
                return True
        return False

    def _add_permissions(self, obj, data):
        """Add permissions to `data` for `obj` based on the current user."""
        # Only `edit` and `delete` are used because if the user cannot view
        # then it will not call this method at all and create is a global
        # action that is not scoped to an object.
        has_permissions = (
            self._meta.edit_permission is not None
            or self._meta.delete_permission is not None
        )
        if not has_permissions:
            return data
        permissions = []
        if self._meta.edit_permission is not None and self.user.has_perm(
            self._meta.edit_permission, obj
        ):
            permissions.append("edit")
        if self._meta.delete_permission is not None and self.user.has_perm(
            self._meta.delete_permission, obj
        ):
            permissions.append("delete")
        data["permissions"] = permissions
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
            if (
                non_changeable_fields is not None
                and field_name in non_changeable_fields
            ):
                continue

            # Update the field if its in the provided data. Passing the value
            # through its hydrate method if present.
            if field_name in data:
                value = data[field_name]
                hydrate_method = getattr(self, "hydrate_%s" % field_name, None)
                if hydrate_method is not None:
                    value = hydrate_method(value)
                if self._is_foreign_key_for(field_name, obj, value):
                    # We're trying to populate a foreign key relationship, but
                    # we don't have a model object. Assume we were given the
                    # primary key.
                    field_name += "_id"
                setattr(obj, field_name, value)

        # Return the hydrated object once its done the final hydrate.
        return self.hydrate(obj, data)

    def hydrate(self, obj, data):
        """Add any extra info to the `obj` before finalizing the finale object.

        :param obj: obj being hydrated.
        :param data: dictionary to use to set object.
        """
        return obj

    def _get_object(self, params, permission=None):
        """Get object by using the `pk` in `params`."""
        if self._meta.pk not in params:
            raise HandlerValidationError(
                {self._meta.pk: ["This field is required"]}
            )
        pk = params[self._meta.pk]
        try:
            obj = self.get_queryset(for_list=False).get(**{self._meta.pk: pk})
        except self._meta.object_class.DoesNotExist:
            raise HandlerDoesNotExistError(
                f"Object with id ({pk}) does not exist"
            )
        if permission is not None or self._meta.view_permission is not None:
            if permission is None:
                permission = self._meta.view_permission
            if not self.user.has_perm(permission, obj):
                raise HandlerPermissionError()
        return obj

    def get_object(self, params, permission=None):
        """Get object by using the `pk` in `params`."""
        return self._get_object(params, permission=permission)

    def get_own_object(self, params, permission=None):
        """Get user-owned object by using the `pk` in `params`."""
        obj = self._get_object(params, permission=permission)
        if obj.user != self.user:
            # Error message should be the same as one thrown from super() call
            raise HandlerDoesNotExistError(
                f"Object with id ({params[self._meta.pk]}) does not exist"
            )
        return obj

    def get_queryset(self, use_sqlalchemy_list=False, for_list=False):
        """Return `QuerySet` used by this handler.

        Override if you need to modify the queryset based on the current user.
        """
        if for_list and self._meta.list_queryset is not None:
            if use_sqlalchemy_list:
                return self._meta.use_sqlalchemy_list
            else:
                return self._meta.list_queryset
        else:
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

    def _apiserver_execute(self, method, params):
        return concurrency.webapp.run(deferToThread, method, params)

    def _legacy_execute(self, method, method_name, params):
        # Handler methods are predominantly transactional and thus
        # blocking/synchronous. Genuinely non-blocking/asynchronous
        # methods must out themselves explicitly.
        if IAsynchronous.providedBy(method) or asyncio.iscoroutinefunction(
            method
        ):
            # Running in the io thread so clear RBAC now.
            rbac.clear()

            # Reload the user from the database.
            d = concurrency.webapp.run(
                deferToDatabase,
                transactional(self.user.refresh_from_db),
            )
            d.addCallback(lambda _: ensureDeferred(method(params)))
            return d
        else:

            @wraps(method)
            @transactional
            def prep_user_execute(params):
                # Clear RBAC and reload the user to ensure that
                # its up to date. `rbac.clear` must be done inside
                # the thread because it uses thread locals internally.
                rbac.clear()
                self.user.refresh_from_db()

                # Perform the work in the database.
                return self._call_method_track_queries(
                    method_name, method, params
                )

            # Force the name of the function to include the handler
            # name so the debug logging is useful.
            prep_user_execute.__name__ = "{}.{}".format(
                self.__class__.__name__,
                method_name,
            )

            # This is going to block and hold a database connection so
            # we limit its concurrency.
            return concurrency.webapp.run(
                deferToDatabase, prep_user_execute, params
            )

    @PROMETHEUS_METRICS.record_call_latency(
        "maas_websocket_call_latency",
        get_labels=_get_call_latency_metrics_label,
    )
    @asynchronous
    def execute(self, method_name, params):
        """Execute the given method on the handler.

        Checks to make sure the method is valid and allowed perform executing
        the method.
        """
        if method_name in self._meta.allowed_methods:
            try:
                method = getattr(self, method_name)
            except AttributeError:
                raise HandlerNoSuchMethodError(method_name)
            else:
                if method_name in self._meta.methods_using_apiserver:
                    return self._apiserver_execute(method, params)
                else:
                    return self._legacy_execute(method, method_name, params)
        else:
            raise HandlerNoSuchMethodError(method_name)

    def _call_method_track_queries(self, method_name, method, params):
        """Call the specified method tracking query-related metrics."""
        latencies = []

        with wrap_query_counter_cursor(latencies):
            result = method(params)

        labels = _get_call_latency_metrics_label((self, method_name))
        PROMETHEUS_METRICS.update(
            "maas_websocket_call_query_count",
            "observe",
            value=len(latencies),
            labels=labels,
        )
        for latency in latencies:
            PROMETHEUS_METRICS.update(
                "maas_websocket_call_query_latency",
                "observe",
                value=latency,
                labels=labels,
            )

        return result

    def _cache_pks(self, objs):
        """Cache all loaded object pks."""
        getpk = attrgetter(self._meta.pk)
        objs = list(objs)
        self.cache["loaded_pks"].update(getpk(obj) for obj in objs)
        return objs

    def _filter(self, qs, action, params):
        """Return a filtered queryset

        Currently a NOP, override with the required logic.
        """
        return qs

    def _sort(self, qs, action, params, keys=None):
        """Return a sorted queryset"""
        keys = keys or []

        if params.get("sort_key"):
            desc = (
                "-"
                if (params.get("sort_direction", None) == "descending")
                else ""
            )
            keys.append(f"{desc}{self._get_group_expr(params['sort_key'])}")

        keys.append(self._meta.batch_key)

        return qs.order_by(*keys)

    def _collapse_groups(self, qs, grp_key, collapsed):
        """Exclude collapsed groups from results"""
        return qs.exclude(**{f"{grp_key}__in": collapsed})

    def _get_group_expr(self, key):
        """Get grouping expression for key"""
        return key

    def _get_group_label(self, key, value):
        """Get group label for value"""
        if value is None:
            return "None"
        else:
            return value

    def _get_group_value(self, key, value):
        """Get form value for DB value"""
        return value

    def _xlate_group_id(self, key, value):
        """Translate group id to DB"""
        return value

    def _load_extra_data_before_dehydrate(self, objs, for_list=False):
        """Load additional data before dehydrate logic.

        Currently a NOP, override with the required logic.
        """
        return None

    def list(
        self, params, use_sqlalchemy_list=False, full_dehydrate_function=None
    ):
        """List objects.

        :param start: A value of the `batch_key` column and NOT `pk`. They are
            often the same but that is not a certainty. Make sure the client
            also understands this distinction.
        :param start: Offset into the queryset to return.
        :param limit: Maximum number of objects to return.
        :param page_size: Number of items per page.
        :param page_number: Request a specific page.
        :param filter: a filter for the list. The `_filter()` method MUST be
            overridden to implement the desired DSL.
        :param sort_key: desired sorting key
        """
        if full_dehydrate_function is None:
            full_dehydrate_function = self.full_dehydrate

        if use_sqlalchemy_list:
            qs_filter = self.get_queryset(
                use_sqlalchemy_list=use_sqlalchemy_list, for_list=True
            )
        else:
            qs_filter = self.get_queryset(for_list=True)

        if "filter" in params:
            qs_filter = self._filter(qs_filter, "list", params["filter"])

        if self._meta.use_paginated_list:
            return self._build_list_grouping(
                qs_filter, params, full_dehydrate_function
            )
        else:
            return self._build_list_simple(qs_filter, params)

    def _build_list_simple(self, qs, params):
        """List objects using simple schema.

        :param start: A value of the `batch_key` column and NOT `pk`. They are
            often the same but that is not a certainty. Make sure the client
            also understands this distinction.
        :param start: Offset into the queryset to return.
        :param limit: Maximum number of objects to return.
        """
        qs = self._sort(qs, "list", params)
        if "start" in params:
            qs = qs.filter(**{f"{self._meta.batch_key}__gt": params["start"]})
        if "limit" in params:
            qs = qs[: params["limit"]]
        objs = self._cache_pks(qs)
        self._load_extra_data_before_dehydrate(qs, True)
        return [self.full_dehydrate(obj, for_list=True) for obj in objs]

    def _build_list_grouping(self, qs, params, full_dehydrate_function):
        """List objects with grouping and pagination.

        :param page_size: Number of items per page.
        :param page_number: Request a specific page.
        :param filter: a filter for the list. The `_filter()` method MUST be
            overridden to implement the desired DSL.
        :param sort_key: desired sorting key
        :param group_key: grouping key
        :param group_collapsed: list of groups to suppress from output
        """

        def new_grp(label, key, count, collapsed):
            return {
                "name": label,
                "value": key,
                "count": count,
                "collapsed": collapsed,
                "items": list(),
            }

        grp_key = params.get("group_key")
        grp_expr = self._get_group_expr(grp_key)

        collapsed = [
            self._xlate_group_id(grp_key, id)
            for id in params.get("group_collapsed", [])
        ]

        qs = self._sort(qs, "list", params, [grp_expr] if grp_expr else [])
        page_size = params.get("page_size", self._meta.dft_page_size)
        if not grp_key or not collapsed:
            # No collapsed groups, so the original query is what we
            # want to paginate through.
            pager = Paginator(qs, page_size)
            qs_list = qs
            # This is a cached property on the Paginator which saves a query \o/
            count = pager.count
        else:
            # Collapsed groups so we have to figure those out and
            # derive the count separately.
            qs_list = self._collapse_groups(qs, grp_expr, collapsed)
            pager = Paginator(qs_list, page_size)
            count = qs.count()

        current_page = pager.get_page(params.get("page_number", 1))
        page_objs = self._cache_pks(current_page)
        self._load_extra_data_before_dehydrate(current_page, True)

        result = {
            "count": count,
            "cur_page": current_page.number,
            "num_pages": pager.num_pages,
        }

        if grp_key:

            def get_group_key(attr):
                def _get_id(obj):
                    return reduce(
                        lambda o, a: getattr(o, a, None),
                        [obj] + attr.split("__"),
                    )

                return _get_id

            gid_getter = get_group_key(grp_expr)
            qs_grouping = Q()

            if current_page.has_previous():
                # start_index() is 1-based index
                # None is always last, so there's nothing after
                bottom_prev_page = gid_getter(
                    qs_list[(current_page.start_index() - 1) - 1]
                )
                if bottom_prev_page is None:
                    qs_grouping &= Q(**{f"{grp_expr}__isnull": True})
                else:
                    top_this_page = gid_getter(page_objs[0])
                    cmp = "gte" if top_this_page == bottom_prev_page else "gt"
                    qs_grouping &= Q(
                        **{f"{grp_expr}__{cmp}": bottom_prev_page}
                    ) | Q(**{f"{grp_expr}__isnull": True})

            if current_page.has_next():
                bottom_this_page = gid_getter(page_objs[-1])
                if bottom_this_page is not None:
                    qs_grouping &= Q(**{f"{grp_expr}__lte": bottom_this_page})

            groups_visible = (
                qs.filter(qs_grouping)
                .values(**{"grp_id": F(grp_expr)})
                .annotate(total=Count(self._meta.batch_key, distinct=True))
                .order_by(grp_expr)
            )

            groups = dict()
            for g in groups_visible:
                grp_id = g["grp_id"]
                groups[grp_id] = new_grp(
                    self._get_group_label(grp_key, grp_id),
                    self._get_group_value(grp_key, grp_id),
                    g["total"],
                    grp_id in collapsed,
                )

            for obj in page_objs:
                grp_id = gid_getter(obj)
                groups[grp_id]["items"].append(
                    full_dehydrate_function(obj, for_list=True)
                )
            result["groups"] = list(groups.values())
        else:
            grp = new_grp(None, None, result["count"], False)
            grp["items"] = [
                full_dehydrate_function(obj, for_list=True)
                for obj in page_objs
            ]
            result["groups"] = [grp]

        return result

    def get(self, params):
        """Get object.

        :param pk: Object with primary key to return.
        """
        obj = self.get_object(params)
        self._cache_pks([obj])
        self._load_extra_data_before_dehydrate([obj], False)
        return self.full_dehydrate(obj)

    def create(self, params):
        """Create the object from data."""
        obj = self._create(params)
        return self.full_dehydrate(obj)

    def _create(self, params):
        # Create by using form. `create_permission` is not used with form,
        # permission checks should be done in the form.
        form_class = self.get_form_class("create")
        if form_class is not None:
            data = self.preprocess_form("create", params)
            if self._meta.form_requires_request:
                form = form_class(request=self.request, data=data)
            else:
                form = form_class(data=data)
            if hasattr(form, "use_perms") and form.use_perms():
                if not form.has_perm(self.user):
                    raise HandlerPermissionError()
            elif self._meta.create_permission is not None:
                raise ValueError(
                    "`create_permission` defined on the handler, but the form "
                    "is not using permission checks."
                )
            if form.is_valid():
                try:
                    obj = form.save()
                except ValidationError as e:
                    try:
                        raise HandlerValidationError(e.message_dict)
                    except AttributeError:
                        raise HandlerValidationError({"__all__": e.message})
                return self.refetch(obj)
            else:
                raise HandlerValidationError(form.errors)

        # Verify the user can create an object.
        if self._meta.create_permission is not None:
            if not self.user.has_perm(self._meta.create_permission):
                raise HandlerPermissionError()

        # Create by updating the fields on the object.
        obj = self._meta.object_class()
        obj = self.full_hydrate(obj, params)
        obj.save()
        return obj

    def update(self, params):
        """Update the object."""
        obj = self.get_object(params)
        obj = self._update(obj, params)
        return self.full_dehydrate(obj)

    def _update(self, obj, params):
        # Update by using form. `edit_permission` is not used when form
        # is used to update. The form should define the permissions.
        form_class = self.get_form_class("update")
        if form_class is not None:
            data = self.preprocess_form("update", params)
            form = form_class(data=data, instance=obj)
            if hasattr(form, "use_perms") and form.use_perms():
                if not form.has_perm(self.user):
                    raise HandlerPermissionError()
            elif self._meta.edit_permission is not None:
                raise ValueError(
                    "`edit_permission` defined on the handler, but the form "
                    "is not using permission checks."
                )
            if form.is_valid():
                try:
                    obj = form.save()
                except ValidationError as e:
                    raise HandlerValidationError(e.error_dict)
                return obj
            else:
                raise HandlerValidationError(form.errors)

        # Verify the user can edit this object.
        if self._meta.edit_permission is not None:
            if not self.user.has_perm(self._meta.edit_permission, obj):
                raise HandlerPermissionError()

        # Update by updating the fields on the object.
        obj = self.full_hydrate(obj, params)
        obj.save()
        return obj

    def delete(self, params):
        """Delete the object."""
        obj = self.get_object(params, permission=self._meta.delete_permission)
        self._delete(obj)

    def _delete(self, obj):
        obj.delete()

    def set_active(self, params):
        """Set the active node for this connection.

        This is the node that is being viewed in detail by the client.
        """
        # Calling this method without a primary key will clear the currently
        # active object.
        if self._meta.pk not in params:
            if "active_pk" in self.cache:
                del self.cache["active_pk"]
            return

        # Get the object data and set it as active.
        obj_data = self.get(params)
        self.cache["active_pk"] = obj_data[self._meta.pk]
        return obj_data

    def on_listen(self, channel, action, pk):
        """Called by the protocol when a channel notification occurs.

        Do not override this method instead override `listen`.
        """
        pk = self._meta.pk_type(pk)
        if action == "delete":
            if pk in self.cache["loaded_pks"]:
                self.cache["loaded_pks"].remove(pk)
                return (self._meta.handler_name, action, pk)
            else:
                return None

        self.user.refresh_from_db()
        try:
            obj = self.listen(channel, action, pk)
        except HandlerDoesNotExistError:
            obj = None
        if action == "create" and obj is not None:
            if pk in self.cache["loaded_pks"]:
                # The user already knows about this node, so its not a create
                # to the user but an update.
                return self.on_listen_for_active_pk("update", pk, obj)
            else:
                self.cache["loaded_pks"].add(pk)
                return self.on_listen_for_active_pk(action, pk, obj)
        elif action == "update":
            if pk in self.cache["loaded_pks"]:
                if obj is None:
                    # The user no longer has access to this object. To the
                    # client this is a delete action.
                    self.cache["loaded_pks"].remove(pk)
                    return (self._meta.handler_name, "delete", pk)
                else:
                    # Just a normal update to the client.
                    return self.on_listen_for_active_pk(action, pk, obj)
            elif obj is not None:
                # User just got access to this new object. Send the message to
                # the client as a create action instead of an update.
                self.cache["loaded_pks"].add(pk)
                return self.on_listen_for_active_pk("create", pk, obj)
            else:
                # User doesn't have access to this object, so do nothing.
                pass
        else:
            # Unknown action or the user doesn't have permission to view the
            # newly created object, so do nothing.
            pass
        return None

    def on_listen_for_active_pk(self, action, pk, obj):
        """Return the correct data for `obj` depending on if its the
        active primary key."""
        if "active_pk" in self.cache and pk == self.cache["active_pk"]:
            # Active so send all the data for the object.
            return (
                self._meta.handler_name,
                action,
                self.full_dehydrate(obj, for_list=False),
            )
        else:
            # Not active so only send the data like it was comming from
            # the list call.
            return (
                self._meta.handler_name,
                action,
                self.full_dehydrate(obj, for_list=True),
            )

    def listen(self, channel, action, pk):
        """Called when the handler listens for events on channels with
        `Meta.listen_channels`.

        :param channel: Channel event occured on.
        :param action: Action that caused this event.
        :param pk: Id of the object.
        """
        return self.get_object({self._meta.pk: pk})

    def refetch(self, obj):
        """Refetch an object using the handler queryset.

        This ensures annotations defined in the queryset are added to the
        object.
        """
        return self.get_object({self._meta.pk: getattr(obj, self._meta.pk)})

    def unsubscribe(self, params):
        if self._meta.pk in params:
            pk = params[self._meta.pk]
            if pk == self.cache.get("active_pk"):
                del self.cache["active_pk"]
            self.cache["loaded_pks"] = self.cache["loaded_pks"] - set(pk)
            return [pk]
        elif self._meta.bulk_pk in params:
            pks = set(params[self._meta.bulk_pk])
            if self.cache.get("active_pk") in pks:
                del self.cache["active_pk"]
            self.cache["loaded_pks"] = self.cache["loaded_pks"] - pks
            return list(pks)
        else:
            raise HandlerValidationError(
                f"'{self._meta.pk}' or '{self._meta.bulk_pk}' must be provided in params for unsubscribe"
            )


class AdminOnlyMixin(Handler):
    class Meta:
        abstract = True

    def create(self, parameters):
        """Only allow an administrator to create this object."""
        if not self.user.has_perm(
            NodePermission.admin, self._meta.object_class
        ):
            raise HandlerPermissionError()
        return super().create(parameters)

    def update(self, parameters):
        """Only allow an administrator to update this object."""
        obj = self.get_object(parameters)
        if not self.user.has_perm(NodePermission.admin, obj):
            raise HandlerPermissionError()
        return super().update(parameters)

    def delete(self, parameters):
        """Only allow an administrator to delete this object."""
        obj = self.get_object(parameters)
        if not self.user.has_perm(NodePermission.admin, obj):
            raise HandlerPermissionError()
        return super().delete(parameters)
