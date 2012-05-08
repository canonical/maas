# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model mixin: check `full_clean` on every `save`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'CleanSave',
    ]


class CleanSave:
    """Mixin for model classes.

    This adds a call to `self.full_clean` to every `save`, so that you can
    never save a model object in an unaccepted state.

    This was meant to be a standard part of Django model classes, but was
    left out purely for backwards compatibility_, which is not an issue for
    us.

    Derive your model from :class:`CleanSave` before deriving from
    :class:`django.db.models.Model` if you need the `full_clean` to happen
    before the real `save` to the database.

    .. _compatibility: https://code.djangoproject.com/ticket/13100#comment:2
    """
    def save(self, *args, **kwargs):
        self.full_clean()
        return super(CleanSave, self).save(*args, **kwargs)
