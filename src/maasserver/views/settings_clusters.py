# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Cluster Settings views."""

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
from maasserver.forms import (
    NodeGroupEdit,
    NodeGroupInterfaceForm,
    )
from maasserver.models import (
    NodeGroup,
    NodeGroupInterface,
    )


class ClusterEdit(UpdateView):
    model = NodeGroup
    template_name = 'maasserver/nodegroup_edit.html'
    form_class = NodeGroupEdit
    context_object_name = 'cluster'

    def get_context_data(self, **kwargs):
        context = super(ClusterEdit, self).get_context_data(**kwargs)
        context['interfaces'] = (
            self.object.nodegroupinterface_set.all().order_by('interface'))
        return context

    def get_success_url(self):
        return reverse('settings')

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
        return reverse('settings')

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
        interface = self.kwargs.get('interface', None)
        return get_object_or_404(
            NodeGroupInterface, nodegroup__uuid=uuid, interface=interface)

    def get_next_url(self):
        uuid = self.kwargs.get('uuid', None)
        return reverse('cluster-edit', args=[uuid])

    def delete(self, request, *args, **kwargs):
        interface = self.get_object()
        interface.delete()
        messages.info(request, "Interface %s deleted." % interface.interface)
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
        interface = self.kwargs.get('interface', None)
        return get_object_or_404(
            NodeGroupInterface, nodegroup__uuid=uuid, interface=interface)


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
