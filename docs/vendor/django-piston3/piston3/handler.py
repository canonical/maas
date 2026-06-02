import warnings

from django.conf import settings
from django.core.exceptions import (
    MultipleObjectsReturned,
    ObjectDoesNotExist,
)

from .utils import rc

typemapper = {}
handler_tracker = []


class HandlerMetaClass(type):
    """
    Metaclass that keeps a registry of class -> handler
    mappings.
    """

    def __new__(cls, name, bases, attrs):
        new_cls = type.__new__(cls, name, bases, attrs)

        def already_registered(model, anon):
            for k, (m, a) in typemapper.items():
                if model == m and anon == a:
                    return k

        if hasattr(new_cls, "model"):
            if already_registered(new_cls.model, new_cls.is_anonymous):
                if not getattr(settings, "PISTON_IGNORE_DUPE_MODELS", False):
                    warnings.warn(
                        f"Handler already registered for model {new_cls.model.__name__}, "
                        "you may experience inconsistent results."
                    )

            typemapper[new_cls] = (new_cls.model, new_cls.is_anonymous)
        else:
            typemapper[new_cls] = (None, new_cls.is_anonymous)

        if name not in ("BaseHandler", "AnonymousBaseHandler"):
            handler_tracker.append(new_cls)

        return new_cls


class BaseHandler(metaclass=HandlerMetaClass):
    """
    Basehandler that gives you CRUD for free.
    You are supposed to subclass this for specific
    functionality.

    All CRUD methods (`read`/`update`/`create`/`delete`)
    receive a request as the first argument from the
    resource. Use this for checking `request.user`, etc.
    """

    allowed_methods = ("GET", "POST", "PUT", "DELETE")
    anonymous = is_anonymous = False
    exclude = ("id",)
    fields = ()

    def flatten_dict(self, dct):
        return dict([(str(k), dct.get(k)) for k in dct.keys()])

    def has_model(self):
        return hasattr(self, "model") or hasattr(self, "queryset")

    def queryset(self, request):
        return self.model.objects.all()

    def value_from_tuple(tu, name):
        for int_, n in tu:
            if n == name:
                return int_
        return None

    def exists(self, **kwargs):
        if not self.has_model():
            raise NotImplementedError

        try:
            self.model.objects.get(**kwargs)
            return True
        except self.model.DoesNotExist:
            return False

    def read(self, request, *args, **kwargs):
        if not self.has_model():
            return rc.NOT_IMPLEMENTED

        pkfield = self.model._meta.pk.name

        if pkfield in kwargs:
            try:
                return self.queryset(request).get(pk=kwargs.get(pkfield))
            except ObjectDoesNotExist:
                return rc.NOT_FOUND
            except (
                MultipleObjectsReturned
            ):  # should never happen, since we're using a PK
                return rc.BAD_REQUEST
        else:
            return self.queryset(request).filter(*args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not self.has_model():
            return rc.NOT_IMPLEMENTED

        attrs = self.flatten_dict(request.data)

        try:
            inst = self.queryset(request).get(**attrs)
            return rc.DUPLICATE_ENTRY
        except self.model.DoesNotExist:
            inst = self.model(**attrs)
            inst.save()
            return inst
        except self.model.MultipleObjectsReturned:
            return rc.DUPLICATE_ENTRY

    def update(self, request, *args, **kwargs):
        if not self.has_model():
            return rc.NOT_IMPLEMENTED

        pkfield = self.model._meta.pk.name

        if pkfield not in kwargs:
            # No pk was specified
            return rc.BAD_REQUEST

        try:
            inst = self.queryset(request).get(pk=kwargs.get(pkfield))
        except ObjectDoesNotExist:
            return rc.NOT_FOUND
        except (
            MultipleObjectsReturned
        ):  # should never happen, since we're using a PK
            return rc.BAD_REQUEST

        attrs = self.flatten_dict(request.data)
        for k, v in attrs.items():
            setattr(inst, k, v)

        inst.save()
        return rc.ALL_OK

    def delete(self, request, *args, **kwargs):
        if not self.has_model():
            raise NotImplementedError

        try:
            inst = self.queryset(request).get(*args, **kwargs)

            inst.delete()

            return rc.DELETED
        except self.model.MultipleObjectsReturned:
            return rc.DUPLICATE_ENTRY
        except self.model.DoesNotExist:
            return rc.NOT_HERE


class AnonymousBaseHandler(BaseHandler):
    """
    Anonymous handler.
    """

    is_anonymous = True
    allowed_methods = ("GET",)
