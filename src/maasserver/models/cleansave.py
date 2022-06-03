# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model mixin: track field states and `full_clean` on every `save`."""


from copy import copy

from django.core.exceptions import FieldDoesNotExist
from django.db.models.base import ModelState

# Used to track that the field was unset.
FieldUnset = object()


class CleanSaveModelState(ModelState):
    """Provides helpers on `_state` attribute on a model."""

    def __init__(self):
        super().__init__()
        self._changed_fields = {}

    def has_any_changed(self, names):
        """Return `True` if any of the provided field names have changed."""
        return max(name in self._changed_fields for name in names)


class CleanSave:
    """Mixin for model classes.

    This adds field state tracking, a call to `self.full_clean` to every
    `save` and only saving changed fields to the database. With tracking
    code can perform actions and checks based on what has changed instead
    of against the whole model. The `self.full_clean` before save ensures that
    a model cannot be saved in a bad state. `self.full_clean` should only
    do checks based on changed fields to reduce the required work and the
    query count.

    Derive your model from :class:`CleanSave` before deriving from
    :class:`django.db.models.Model` if you need field state tracking and for
    `self.full_clean` to happen before the real `save` to the database.

    .. _compatibility: https://code.djangoproject.com/ticket/13100#comment:2
    """

    @classmethod
    def from_db(cls, db, field_names, values):
        new = super().from_db(db, field_names, values)
        new._state._changed_fields = {}
        return new

    def refresh_from_db(self, using=None, fields=None):
        super().refresh_from_db(using=using, fields=fields)
        # Revert the changed-state for the fields that we reload, so
        # that they will be saved if changed later.
        if fields is None:
            self._state._changed_fields = {}
        else:
            for field in fields:
                if field in self._state._changed_fields:
                    del self._state._changed_fields[field]

    def __marked_changed(self, name, old_value, new_value):
        """Marks the field changed or not depending on the values."""
        if old_value != new_value:
            if name in self._state._changed_fields:
                if self._state._changed_fields[name] == new_value:
                    # Reverted, no longer changed.
                    self._state._changed_fields.pop(name)
            else:
                try:
                    self._state._changed_fields[name] = copy(old_value)
                except TypeError:
                    # Object cannot be copied so we assume the object is
                    # immutable and set the old value to the object.
                    self._state._changed_fields[name] = old_value

    def __setattr__(self, name, value):
        """Track the fields that have changed."""
        # Prepare the field tracking inside the `_state`. Don't track until
        # the `_state` is set on the model.
        if name == "_state":
            # Override the class of the `_state` attribute to be the
            # `CleanSaveModelState`. This provides the helpers for determining
            # if a field has changed.
            value.__class__ = CleanSaveModelState
            value._changed_fields = {}
            return super().__setattr__(name, value)
        if not hasattr(self, "_state"):
            return super().__setattr__(name, value)

        try:
            field = self._meta.get_field(name)
        except FieldDoesNotExist:
            prop_obj = getattr(self.__class__, name, None)
            if isinstance(prop_obj, property):
                if prop_obj.fset is None:
                    raise AttributeError("can't set attribute")
                prop_obj.fset(self, value)
            else:
                super().__setattr__(name, value)
        else:

            def _wrap_setattr():
                # Wrap `__setattr__` to track the changes.
                if self._state.adding:
                    # Adding a new model so no old values exist in the
                    # database, so all previous values are None.
                    super(CleanSave, self).__setattr__(name, value)
                    self.__marked_changed(name, None, value)
                else:
                    old = getattr(self, name, FieldUnset)
                    super(CleanSave, self).__setattr__(name, value)
                    new = getattr(self, name, FieldUnset)
                    self.__marked_changed(name, old, new)

            if not field.is_relation:
                # Simple field that just stores a value and is not related
                # to another model. Just track the difference between the
                # new and old value.
                _wrap_setattr()
            elif field.one_to_one or (
                field.many_to_one and field.related_model
            ):
                if name == field.attname:
                    # Field that stores the relation field ending in `_id`.
                    # This is updated just like a non-relational field.
                    _wrap_setattr()
                elif name == field.name:
                    # Field that holds the actual referenced objects. Ignore
                    # tracking because the related descriptor will set the
                    # related primary key for the field.
                    super().__setattr__(name, value)
                else:
                    raise AttributeError(f"Unknown field({name}) for: {field}")
            else:
                super().__setattr__(name, value)

    def save(self, *args, **kwargs):
        """Perform `full_clean` before save and only save changed fields."""
        exclude_clean_fields = (
            {self._meta.pk.name}
            | {field.name for field in self._meta.fields if field.is_relation}
            | {
                f.attname
                for f in self._meta.concrete_fields
                if f.attname not in self.__dict__
            }
        )
        if (
            "update_fields" in kwargs
            or kwargs.get("force_insert", False)
            or kwargs.get("force_update", False)
            or self.pk is None
            or self._state.adding
            or self._meta.pk.attname in self._state._changed_fields
        ):
            # Nothing has changed, but parameters passed requires a save to
            # occur. Perform the same validation as above for the default
            # Django path, with the exceptions.
            self.full_clean(
                exclude=exclude_clean_fields, validate_unique=False
            )
            self.validate_unique(exclude=[self._meta.pk.name])
            return super().save(*args, **kwargs)
        elif self._state._changed_fields:
            # This is the new path where saving only updates the fields
            # that have actually changed.
            kwargs["update_fields"] = {
                key
                for key, value in self._state._changed_fields.items()
                if value is not FieldUnset
            }

            # Exclude the related fields and fields that didn't change
            # in the validation.
            exclude_clean_fields |= {
                field.name
                for field in self._meta.fields
                if field.attname not in kwargs["update_fields"]
            }
            self.full_clean(
                exclude=exclude_clean_fields, validate_unique=False
            )

            # Validate uniqueness only for fields that have changed and
            # never the primary key.
            exclude_unique_fields = {self._meta.pk.name} | {
                field.name
                for field in self._meta.fields
                if field.attname not in kwargs["update_fields"]
            }
            self.validate_unique(exclude=exclude_unique_fields)

            # Re-create the update_fields from `_changed_fields` after
            # performing clean because some clean methods will modify
            # fields on the model.
            kwargs["update_fields"] = {
                key
                for key, value in self._state._changed_fields.items()
                if value is not FieldUnset
            }
            return super().save(*args, **kwargs)
        else:
            # Nothing changed so nothing needs to be saved.
            return self

    def _save_table(
        self,
        raw=False,
        cls=None,
        force_insert=False,
        force_update=False,
        using=None,
        update_fields=None,
    ):
        """
        Do the heavy-lifting involved in saving. Update or insert the data
        for a single table.

        This is overridden to update `update_fields` with `_changed_fields`
        because some `pre_save` signals can modify fields on a model. Also
        it clears the `_changed_fields` before `post_save` signal is fired.
        """
        if update_fields is not None:
            update_fields = update_fields.union(
                {
                    key
                    for key, value in self._state._changed_fields.items()
                    if value is not FieldUnset
                }
            )
            update_fields = frozenset(update_fields)
        res = super()._save_table(
            raw=raw,
            cls=cls,
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
        self._state._changed_fields = {}
        return res
