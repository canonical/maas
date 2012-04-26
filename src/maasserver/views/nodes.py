# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Nodes views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'NodeListView',
    'NodeView',
    'NodeEdit',
    ]

from logging import getLogger

from django.conf import settings as django_settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.views.generic import (
    ListView,
    UpdateView,
    )
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    )
from maasserver.exceptions import (
    MAASAPIException,
    NoRabbit,
    )
from maasserver.forms import (
    get_action_form,
    UIAdminNodeEditForm,
    UINodeEditForm,
    )
from maasserver.messages import messaging
from maasserver.models import Node
from maasserver.views import HelpfulDeleteView


def get_longpoll_context():
    if messaging is not None and django_settings.LONGPOLL_PATH is not None:
        try:
            return {
                'longpoll_queue': messaging.getQueue().name,
                'LONGPOLL_PATH': django_settings.LONGPOLL_PATH,
                }
        except NoRabbit as e:
            getLogger('maasserver').warn(
                "Could not connect to RabbitMQ: %s", e)
            return {}
    else:
        return {}


class NodeListView(ListView):

    context_object_name = "node_list"

    def get_queryset(self):
        # Return node list sorted, newest first.
        return Node.objects.get_nodes(
            user=self.request.user,
            perm=NODE_PERMISSION.VIEW).order_by('-created')

    def get_context_data(self, **kwargs):
        context = super(NodeListView, self).get_context_data(**kwargs)
        context.update(get_longpoll_context())
        return context


# Info message displayed on the node page for COMMISSIONING
# or READY nodes.
NODE_BOOT_INFO = mark_safe("""
You can boot this node using Avahi-enabled boot media or an adequately
configured dhcp server.  See
<a href="https://wiki.ubuntu.com/ServerTeam/MAAS/AvahiBoot">
https://wiki.ubuntu.com/ServerTeam/MAAS/AvahiBoot</a> for instructions.
""")


class NodeView(UpdateView):

    template_name = 'maasserver/node_view.html'

    context_object_name = 'node'

    def get_object(self):
        system_id = self.kwargs.get('system_id', None)
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=self.request.user,
            perm=NODE_PERMISSION.VIEW)
        return node

    def get_form_class(self):
        return get_action_form(self.request.user, self.request)

    def get_context_data(self, **kwargs):
        context = super(NodeView, self).get_context_data(**kwargs)
        node = self.get_object()
        context['can_edit'] = self.request.user.has_perm(
            NODE_PERMISSION.EDIT, node)
        if node.status in (NODE_STATUS.COMMISSIONING, NODE_STATUS.READY):
            messages.info(self.request, NODE_BOOT_INFO)
        context['error_text'] = (
            node.error if node.status == NODE_STATUS.FAILED_TESTS else None)
        context['status_text'] = (
            node.error if node.status != NODE_STATUS.FAILED_TESTS else None)
        return context

    def dispatch(self, *args, **kwargs):
        """Override from Django `View`: Handle MAAS exceptions.

        Node actions may raise exceptions derived from
        :class:`MAASAPIException`.  This type of exception contains an
        http status code that we will forward to the client.
        """
        try:
            return super(NodeView, self).dispatch(*args, **kwargs)
        except MAASAPIException as e:
            return e.make_http_response()

    def get_success_url(self):
        return reverse('node-view', args=[self.get_object().system_id])


class NodeEdit(UpdateView):

    template_name = 'maasserver/node_edit.html'

    def get_object(self):
        system_id = self.kwargs.get('system_id', None)
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=self.request.user,
            perm=NODE_PERMISSION.EDIT)
        return node

    def get_form_class(self):
        if self.request.user.is_superuser:
            return UIAdminNodeEditForm
        else:
            return UINodeEditForm

    def get_success_url(self):
        return reverse('node-view', args=[self.get_object().system_id])


class NodeDelete(HelpfulDeleteView):

    template_name = 'maasserver/node_confirm_delete.html'
    context_object_name = 'node_to_delete'
    model = Node

    def get_object(self):
        system_id = self.kwargs.get('system_id', None)
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=self.request.user,
            perm=NODE_PERMISSION.ADMIN)
        if node.status == NODE_STATUS.ALLOCATED:
            raise PermissionDenied()
        return node

    def get_next_url(self):
        return reverse('node-list')

    def name_object(self, obj):
        """See `HelpfulDeleteView`."""
        return "Node %s" % obj.system_id
