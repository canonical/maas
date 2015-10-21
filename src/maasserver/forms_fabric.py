# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fabric form."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "FabricForm",
]

from maasserver.forms import MAASModelForm
from maasserver.models.fabric import Fabric


class FabricForm(MAASModelForm):
    """Fabric creation/edition form."""

    class Meta:
        model = Fabric
        fields = (
            'name',
            'class_type',
            )
