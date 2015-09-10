# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Space form."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "SpaceForm",
]

from maasserver.forms import MAASModelForm
from maasserver.models.space import Space


class SpaceForm(MAASModelForm):
    """Space creation/edition form."""

    class Meta:
        model = Space
        fields = (
            'name',
            )
