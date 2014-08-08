# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ORM-related test helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'reload_object',
    'reload_objects',
    ]

from maasserver.utils.orm import get_one


def reload_object(model_object):
    """Reload `obj` from the database.

    Use this when a test needs to inspect changes to model objects made by
    the API.

    If the object has been deleted, this will return None.

    :param model_object: Model object to reload.
    :type model_object: Concrete `Model` subtype.
    :return: Freshly-loaded instance of `model_object`, or None.
    :rtype: Same as `model_object`.
    """
    model_class = model_object.__class__
    return get_one(model_class.objects.filter(id=model_object.id))


def reload_objects(model_class, model_objects):
    """Reload `model_objects` of type `model_class` from the database.

    Use this when a test needs to inspect changes to model objects made by
    the API.

    If any of the objects have been deleted, they will not be included in
    the result.

    :param model_class: `Model` class to reload from.
    :type model_class: Class.
    :param model_objects: Objects to reload from the database.
    :type model_objects: Sequence of `model_class` objects.
    :return: Reloaded objects, in no particular order.
    :rtype: Sequence of `model_class` objects.
    """
    assert all(isinstance(obj, model_class) for obj in model_objects)
    return model_class.objects.filter(
        id__in=[obj.id for obj in model_objects])
