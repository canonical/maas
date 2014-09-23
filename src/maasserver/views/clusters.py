# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Cluster views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ClusterDelete",
    "ClusterEdit",
    "ClusterInterfaceCreate",
    "ClusterInterfaceDelete",
    "ClusterInterfaceEdit",
    "ClusterListView",
    ]

from collections import OrderedDict

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.safestring import mark_safe
from django.views.generic import (
    CreateView,
    DeleteView,
    UpdateView,
    )
from django.views.generic.edit import (
    FormMixin,
    ProcessFormView,
    )
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUP_STATUS_CHOICES,
    )
from maasserver.forms import (
    NodeGroupEdit,
    NodeGroupInterfaceForm,
    )
from maasserver.models import (
    NodeGroup,
    NodeGroupInterface,
    )
from maasserver.views import PaginatedListView


class ClusterListView(PaginatedListView, FormMixin, ProcessFormView):
    template_name = 'maasserver/cluster_listing.html'
    context_object_name = "cluster_list"
    status = None

    def get_queryset(self):
        return NodeGroup.objects.filter(
            status=self.status).order_by('cluster_name')

    # A record of the urls used to reach the clusters of different
    # statuses.
    status_links = OrderedDict((
        (NODEGROUP_STATUS.ACCEPTED, 'cluster-list'),
        (NODEGROUP_STATUS.PENDING, 'cluster-list-pending'),
        (NODEGROUP_STATUS.REJECTED, 'cluster-list-rejected'),
    ))

    def make_title_entry(self, status, link_name):
        """Generate an entry as used by make_cluster_listing_title().

        This is a utility method only used by make_cluster_listing_title.
        It is a separate method for clarity and to help testing."""
        link = reverse(link_name)
        status_name = NODEGROUP_STATUS_CHOICES[status][1]
        nb_clusters = NodeGroup.objects.filter(
            status=status).count()
        entry = "%d %s cluster%s" % (
            nb_clusters,
            status_name.lower(),
            's' if nb_clusters != 1 else '')
        if nb_clusters != 0 and status != self.status:
            entry = '<a href="%s">%s</a>' % (link, entry)
        return entry

    def make_cluster_listing_title(self):
        """Generate this view's title with "tabs" for each cluster status.

        Generate a title for this view with the number of clusters for each
        possible status.  The title includes the links to the other listings
        (i.e. if this is the listing for the accepted clusters, include links
        to the listings of the pending/rejected clusters).  The title will be
        of the form: "3 accepted clusters / 1 pending cluster / 2 rejected
        clusters". (This is simpler to do in the view rather than write this
        using the template language.)
        """
        return mark_safe(
            ' / '.join(
                self.make_title_entry(status, link_name)
                for status, link_name in self.status_links.items()))

    def get_context_data(self, **kwargs):
        context = super(ClusterListView, self).get_context_data(**kwargs)
        context['current_count'] = NodeGroup.objects.filter(
            status=self.status).count()
        context['title'] = self.make_cluster_listing_title()
        # Display warnings (no images, cluster not connected) for clusters,
        # but only for the display of 'accepted' clusters.
        context['display_warnings'] = self.status == NODEGROUP_STATUS.ACCEPTED
        context['status'] = self.status
        context['statuses'] = NODEGROUP_STATUS
        context['status_name'] = NODEGROUP_STATUS_CHOICES[self.status][1]
        return context

    def post(self, request, *args, **kwargs):
        """Handle a POST request."""
        if 'mass_accept_submit' in request.POST:
            # Process accept clusters en masse.
            number = NodeGroup.objects.accept_all_pending()
            messages.info(request, "Accepted %d cluster(s)." % number)
            return HttpResponseRedirect(reverse('cluster-list'))

        elif 'mass_reject_submit' in request.POST:
            # Process reject clusters en masse.
            number = NodeGroup.objects.reject_all_pending()
            messages.info(request, "Rejected %d cluster(s)." % number)
            return HttpResponseRedirect(reverse('cluster-list'))

        else:
            # Unknown action: redirect to the cluster listing page (this
            # shouldn't happen).
            return HttpResponseRedirect(reverse('cluster-list'))


class ClusterEdit(UpdateView):
    model = NodeGroup
    template_name = 'maasserver/nodegroup_edit.html'
    form_class = NodeGroupEdit
    context_object_name = 'cluster'

    def get_context_data(self, **kwargs):
        context = super(ClusterEdit, self).get_context_data(**kwargs)
        context['interfaces'] = (
            self.object.nodegroupinterface_set.all().order_by('name'))
        return context

    def get_success_url(self):
        return reverse('cluster-list')

    def get_object(self):
        uuid = self.kwargs.get('uuid', None)
        return get_object_or_404(NodeGroup, uuid=uuid)

    def form_valid(self, form):
        messages.info(self.request, "Cluster updated.")
        return super(ClusterEdit, self).form_valid(form)


class ClusterDelete(DeleteView):

    template_name = 'maasserver/nodegroup_confirm_delete.html'
    context_object_name = 'cluster_to_delete'

    def get_object(self):
        uuid = self.kwargs.get('uuid', None)
        return get_object_or_404(NodeGroup, uuid=uuid)

    def get_next_url(self):
        return reverse('cluster-list')

    def delete(self, request, *args, **kwargs):
        cluster = self.get_object()
        cluster.delete()
        messages.info(request, "Cluster %s deleted." % cluster.cluster_name)
        return HttpResponseRedirect(self.get_next_url())


class ClusterInterfaceDelete(DeleteView):
    template_name = 'maasserver/nodegroupinterface_confirm_delete.html'
    context_object_name = 'interface_to_delete'

    def get_object(self):
        uuid = self.kwargs.get('uuid', None)
        name = self.kwargs.get('name', None)
        return get_object_or_404(
            NodeGroupInterface, nodegroup__uuid=uuid, name=name)

    def get_next_url(self):
        uuid = self.kwargs.get('uuid', None)
        return reverse('cluster-edit', args=[uuid])

    def delete(self, request, *args, **kwargs):
        interface = self.get_object()
        interface.delete()
        messages.info(request, "Interface %s deleted." % interface.name)
        return HttpResponseRedirect(self.get_next_url())


class ClusterInterfaceEdit(UpdateView):
    template_name = 'maasserver/nodegroupinterface_edit.html'
    form_class = NodeGroupInterfaceForm
    context_object_name = 'interface'

    def get_success_url(self):
        uuid = self.kwargs.get('uuid', None)
        return reverse('cluster-edit', args=[uuid])

    def form_valid(self, form):
        messages.info(self.request, "Interface updated.")
        return super(ClusterInterfaceEdit, self).form_valid(form)

    def get_object(self):
        uuid = self.kwargs.get('uuid', None)
        name = self.kwargs.get('name', None)
        return get_object_or_404(
            NodeGroupInterface, nodegroup__uuid=uuid, name=name)


class ClusterInterfaceCreate(CreateView):
    template_name = 'maasserver/nodegroupinterface_new.html'
    form_class = NodeGroupInterfaceForm
    context_object_name = 'interface'

    def get_form_kwargs(self):
        kwargs = super(ClusterInterfaceCreate, self).get_form_kwargs()
        assert kwargs.get('instance', None) is None
        kwargs['instance'] = NodeGroupInterface(nodegroup=self.get_nodegroup())
        return kwargs

    def get_success_url(self):
        uuid = self.kwargs.get('uuid', None)
        return reverse('cluster-edit', args=[uuid])

    def form_valid(self, form):
        self.object = form.save()
        messages.info(self.request, "Interface created.")
        return super(ClusterInterfaceCreate, self).form_valid(form)

    def get_nodegroup(self):
        nodegroup_uuid = self.kwargs.get('uuid', None)
        return get_object_or_404(NodeGroup, uuid=nodegroup_uuid)

    def get_context_data(self, **kwargs):
        context = super(
            ClusterInterfaceCreate, self).get_context_data(**kwargs)
        context['nodegroup'] = self.get_nodegroup()
        return context
