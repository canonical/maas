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
from django.views.generic import DetailView


class ZoneListView(PaginatedListView):

    context_object_name = "zone_list"

    def get_queryset(self):
        return Zone.objects.all().order_by('name')


class ZoneView(DetailView):
    """Mixin class used to fetch a node by system_id.

    The logged-in user must have View permission to access this page.
    """

    context_object_name = 'zone'

    def get_object(self):
        zone_name = self.kwargs.get('name', None)
        zone = Zone.objects.get(name=zone_name)
        return zone
