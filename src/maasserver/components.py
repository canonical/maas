# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS components management."""

__all__ = [
    "discard_persistent_error",
    "get_persistent_error",
    "get_persistent_errors",
    "register_persistent_error",
    ]

from django.db import IntegrityError
from django.utils.safestring import mark_safe
from maasserver.models import ComponentError
from maasserver.utils.orm import (
    get_one,
    transactional,
)


@transactional
def discard_persistent_error(component):
    """Drop the persistent error for `component`.

    :param component: An enum value of :class:`COMPONENT`.
    """
    ComponentError.objects.filter(component=component).delete()


@transactional
def _register_persistent_error(component, error_message):
    component_error, created = ComponentError.objects.get_or_create(
        component=component, defaults={'error': error_message})
    # If we didn't create a new object, we may need to update it if the error
    # message is different.
    if not created and component_error.error != error_message:
        component_error.error = error_message
        component_error.save()


def register_persistent_error(component, error_message):
    """Register a persistent error for `component`.

    :param component: An enum value of :class:`COMPONENT`.
    :param error_message: Human-readable error text.
    """
    try:
        _register_persistent_error(component, error_message)
    except IntegrityError:
        # Silently ignore IntegrityError: this can happen when
        # _register_persistent_error hits a race condition.
        pass
    except:
        raise


def get_persistent_error(component):
    """Return persistent error for `component`, or None."""
    err = get_one(ComponentError.objects.filter(component=component))
    if err is None:
        return None
    else:
        return err.error


def get_persistent_errors():
    """Return list of current persistent error messages."""
    return sorted(
        mark_safe(err.error) for err in ComponentError.objects.all())
