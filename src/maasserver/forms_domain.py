# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Domain form."""

__all__ = [
    "DomainForm",
]

from maasserver.forms import MAASModelForm
from maasserver.models.domain import Domain


class DomainForm(MAASModelForm):
    """Domain creation/edition form."""

    class Meta:
        model = Domain
        fields = (
            'name',
            'authoritative',
            )
