# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Domain form."""

__all__ = [
    "DomainForm",
]

from maasserver.forms import (
    APIEditMixin,
    MAASModelForm,
)
from maasserver.models.domain import Domain


class DomainForm(MAASModelForm):
    """Domain creation/edition form."""

    class Meta:
        model = Domain
        fields = (
            'name',
            'authoritative',
            'ttl',
            )

    def _post_clean(self):
        # ttl=None needs to make it through.  See also APIEditMixin
        self.cleaned_data = {
            key: value
            for key, value in self.cleaned_data.items()
            if value is not None or key == 'ttl'
        }
        super(APIEditMixin, self)._post_clean()
