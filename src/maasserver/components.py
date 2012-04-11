# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS components management."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "discard_persistent_error",
    "get_persistent_errors",
    "persistent_errors",
    "register_persistent_error",
    ]

from collections import Sequence
import threading

from maasserver.provisioning import present_user_friendly_fault


class COMPONENT:
    COBBLER = 'cobbler server'
    PSERV = 'provisioning server'
    IMPORT_ISOS = 'maas-import-isos script'


# Persistent errors are global to a MAAS instance.
# This is a mapping: component -> error message.
_PERSISTENT_ERRORS = {}


_PERSISTENT_ERRORS_LOCK = threading.Lock()


def _display_fault(error):
    return present_user_friendly_fault(error)


def register_persistent_error(component, error):
    with _PERSISTENT_ERRORS_LOCK:
        global _PERSISTENT_ERRORS
        error_message = _display_fault(error)
        _PERSISTENT_ERRORS[component] = error_message


def discard_persistent_error(component):
    with _PERSISTENT_ERRORS_LOCK:
        global _PERSISTENT_ERRORS
        _PERSISTENT_ERRORS.pop(component, None)


def get_persistent_errors():
    return _PERSISTENT_ERRORS.values()


def persistent_errors(exceptions, component):
    """A method decorator used to report if the decorated method ran
    successfully or raised an exception.  If one of the provided exception
    is raised by the decorated method, the component is marked as failing.
    If the method runs successfully, the component is maked as working (
    if any error has been previously reported for this component).
    """
    if not isinstance(exceptions, Sequence):
        exceptions = (exceptions, )

    def wrapper(func):
        def _wrapper(*args, **kwargs):
            try:
                res = func(*args, **kwargs)
                discard_persistent_error(component)
                return res
            except exceptions, e:
                register_persistent_error(component, e)
                raise
        return _wrapper
    return wrapper
