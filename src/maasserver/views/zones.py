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

from apiclient.utils import urlencode
from django.core.urlresolvers import reverse
from django.views.generic import DetailView
from maasserver.models import Zone
from maasserver.views import PaginatedListView


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

    def get_context_data(self, **kwargs):
        context = super(ZoneView, self).get_context_data(**kwargs)
        query_string = urlencode(
            [('query', 'zone=%s' % self.get_object().name)])
        context["node_list_link"] = (
            reverse('node-list') + "?" + query_string)
        return context
