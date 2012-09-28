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

from maasserver.models import ComponentError


class COMPONENT:
    PSERV = 'provisioning server'
    IMPORT_PXE_FILES = 'maas-import-pxe-files script'


def discard_persistent_error(component):
    ComponentError.objects.filter(component=component).delete()


def register_persistent_error(component, error_message):
    discard_persistent_error(component)
    ComponentError.objects.create(component=component, error=error_message)


def get_persistent_errors():
    return sorted(err.error for err in ComponentError.objects.all())
