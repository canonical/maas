# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Space form."""

from maasserver.forms import MAASModelForm
from maasserver.models.space import Space


class SpaceForm(MAASModelForm):
    """Space creation/edition form."""

    class Meta:
        model = Space
        fields = ("name", "description")
