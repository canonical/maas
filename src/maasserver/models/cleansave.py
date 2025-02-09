# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


class CleanSave:
    """Mixin for model classes.

    This adds a call to `self.full_clean` to every
    `save`.

    The `self.full_clean` before save ensures that a model cannot be saved in a
    bad state.

    Derive your model from :class:`CleanSave` before deriving from
    :class:`django.db.models.Model` if you need field state tracking and for
    `self.full_clean` to happen before the real `save` to the database.

    See https://code.djangoproject.com/ticket/13100#comment:2
    """

    def save(self, *args, **kwargs):
        """Perform `full_clean` before save ."""
        # FIXME Remove this once Django3 support is dropped
        HAS_VALIDATE_CONSTRAINTS = hasattr(self, "validate_constraints")

        exclude_clean_fields = (
            {self._meta.pk.name}
            | {field.name for field in self._meta.fields if field.is_relation}
            | {
                f.attname
                for f in self._meta.concrete_fields
                if f.attname not in self.__dict__
            }
        )
        exclude_unique_fields = {self._meta.pk.name}

        update_fields = kwargs.get("update_fields")
        if update_fields:
            unchanged_fields = {
                field.name
                for field in self._meta.fields
                if field.attname not in update_fields
            }
            # exclude fields that didn't change in the validation
            exclude_clean_fields |= unchanged_fields
            # validate uniqueness only for fields that have changed
            exclude_unique_fields |= unchanged_fields

        self.full_clean(
            exclude=exclude_clean_fields,
            validate_unique=False,
            **(
                {"validate_constraints": False}
                if HAS_VALIDATE_CONSTRAINTS
                else {}
            ),
        )
        self.validate_unique(exclude=exclude_unique_fields)
        return super().save(*args, **kwargs)
