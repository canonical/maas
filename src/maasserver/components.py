# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS components management."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "discard_persistent_error",
    "get_persistent_errors",
    "register_persistent_error",
    ]

import threading


class COMPONENT:
    COBBLER = 'cobbler server'
    PSERV = 'provisioning server'
    IMPORT_PXE_FILES = 'maas-import-pxe-files script'


# Persistent errors are global to a MAAS instance.
# This is a mapping: component -> error message.
_PERSISTENT_ERRORS = {}


_PERSISTENT_ERRORS_LOCK = threading.Lock()


def register_persistent_error(component, error_message):
    with _PERSISTENT_ERRORS_LOCK:
        global _PERSISTENT_ERRORS
        _PERSISTENT_ERRORS[component] = error_message


def discard_persistent_error(component):
    with _PERSISTENT_ERRORS_LOCK:
        global _PERSISTENT_ERRORS
        _PERSISTENT_ERRORS.pop(component, None)


def get_persistent_errors():
    return _PERSISTENT_ERRORS.values()
