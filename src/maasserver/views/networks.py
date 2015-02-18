# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Networks views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'NetworkAdd',
    'NetworkDelete',
    'NetworkEdit',
    'NetworkListView',
    'NetworkView',
    ]

from apiclient.utils import urlencode
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.views.generic import (
    CreateView,
    DetailView,
    UpdateView,
    )
from maasserver.forms import NetworkForm
from maasserver.models import Network
from maasserver.views import (
    HelpfulDeleteView,
    PaginatedListView,
    )


class NetworkListView(PaginatedListView):

    context_object_name = "network_list"

    def get_queryset(self):
        return Network.objects.all().order_by('name')


class NetworkView(DetailView):
    """Mixin class used to fetch a network by name."""

    context_object_name = 'network'

    def get_object(self):
        network_name = self.kwargs.get('name', None)
        return get_object_or_404(Network, name=network_name)

    def get_context_data(self, **kwargs):
        context = super(NetworkView, self).get_context_data(**kwargs)
        query_string = urlencode(
            [('query', 'network:%s' % self.get_object().name)])
        context["node_list_link"] = (
            reverse('index') + "#/nodes" + "?" + query_string)
        return context


class NetworkAdd(CreateView):
    """View for creating a network."""

    form_class = NetworkForm
    template_name = 'maasserver/network_add.html'
    context_object_name = 'new_network'

    def get_success_url(self):
        return reverse('network-list')

    def form_valid(self, form):
        messages.info(self.request, "Network added.")
        return super(NetworkAdd, self).form_valid(form)


class NetworkEdit(UpdateView):
    """View for editing a network."""

    model = Network
    form_class = NetworkForm
    template_name = 'maasserver/network_edit.html'

    def get_object(self):
        network_name = self.kwargs.get('name', None)
        return get_object_or_404(Network, name=network_name)

    def get_success_url(self):
        return reverse('network-list')


class NetworkDelete(HelpfulDeleteView):
    """View for deleting a network."""

    template_name = 'maasserver/network_confirm_delete.html'
    context_object_name = 'network_to_delete'
    model = Network

    def get_object(self):
        name = self.kwargs.get('name', None)
        return get_object_or_404(Network, name=name)

    def get_next_url(self):
        return reverse('network-list')

    def name_object(self, obj):
        """See `HelpfulDeleteView`."""
        return "Network %s" % obj.name
