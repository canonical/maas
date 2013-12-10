# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Zones views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'ZoneListView',
    ]

from maasserver.models import (
    Zone,
    )
from maasserver.views import (
    PaginatedListView,
    )


class ZoneListView(PaginatedListView):

    context_object_name = "zone_list"

    def get_queryset(self):
        return Zone.objects.all().order_by('name')
