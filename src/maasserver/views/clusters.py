# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import (
    CreateView,
    DeleteView,
    UpdateView,
)
from django.views.generic.edit import (
    FormMixin,
    ProcessFormView,
)
from maasserver.enum import NODEGROUP_STATUS
from maasserver.forms import (
    NodeGroupEdit,
    NodeGroupInterfaceForm,
)
from maasserver.models import (
    BootResource,
    NodeGroup,
    NodeGroupInterface,
)
from maasserver.views import PaginatedListView


class ClusterListView(PaginatedListView, FormMixin, ProcessFormView):
    template_name = 'maasserver/cluster_listing.html'
    context_object_name = "cluster_list"
    status = None

    def get_queryset(self):
        return NodeGroup.objects.all().order_by('cluster_name')

    def get_context_data(self, **kwargs):
        context = super(ClusterListView, self).get_context_data(**kwargs)
        cluster_count = NodeGroup.objects.count()
        context['current_count'] = cluster_count
        # Display warnings (no images, cluster not connected) for clusters,
        # but only for the display of ENABLED clusters.
        context['display_warnings'] = self.status == NODEGROUP_STATUS.ENABLED
        context['region_has_images'] = BootResource.objects.exists()
        return context


class ClusterEdit(UpdateView):
    model = NodeGroup
    template_name = 'maasserver/nodegroup_edit.html'
    form_class = NodeGroupEdit
    context_object_name = 'cluster'

    def get_form_kwargs(self):
        kwargs = super(ClusterEdit, self).get_form_kwargs()
        # The cluster form has a boolean checkbox.  For those we need to know
        # whether a submission came in from the UI (where omitting the field
        # means "set to False") or from the API (where it means "leave
        # unchanged").
        kwargs['ui_submission'] = True
        return kwargs

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
