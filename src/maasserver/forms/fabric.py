# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fabric form."""

from maasserver.forms import MAASModelForm
from maasserver.models.fabric import Fabric


class FabricForm(MAASModelForm):
    """Fabric creation/edition form."""

    class Meta:
        model = Fabric
        fields = ("name", "description", "class_type")
