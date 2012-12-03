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
    'enlist_preseed_view',
    'MacAdd',
    'MacDelete',
    'NodeListView',
    'NodePreseedView',
    'NodeView',
    'NodeEdit',
    ]

from logging import getLogger

from django.conf import settings as django_settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.shortcuts import (
    get_object_or_404,
    render_to_response,
    )
from django.template import RequestContext
from django.utils.safestring import mark_safe
from django.views.generic import (
    CreateView,
    DetailView,
    UpdateView,
    )
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    )
from maasserver.exceptions import (
    InvalidConstraint,
    MAASAPIException,
    NoRabbit,
    NoSuchConstraint,
    )
from maasserver.forms import (
    get_action_form,
    get_node_edit_form,
    MACAddressForm,
    )
from maasserver.messages import messaging
from maasserver.models import (
    MACAddress,
    Node,
    )
from maasserver.models.node import CONSTRAINTS_JUJU_MAP
from maasserver.models.node_constraint_filter import constrain_nodes
from maasserver.preseed import (
    get_enlist_preseed,
    get_preseed,
    )
from maasserver.views import (
    HelpfulDeleteView,
    PaginatedListView,
    )


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


def _parse_constraints(query_string):
    """Turn query string from user into constraints dict

    This is basically the same as the juju constraints, but will differ
    somewhat in error handling. For instance, juju might reject a negative
    cpu constraint whereas this lets it through to return zero results.
    """
    constraints = {}
    for word in query_string.strip().split():
        parts = word.split("=", 1)
        if parts[0] not in CONSTRAINTS_JUJU_MAP:
            raise NoSuchConstraint(parts[0])
        if len(parts) != 2:
            raise InvalidConstraint(parts[0], "", "No constraint value given")
        if parts[1] and parts[1] != "any":
            constraints[CONSTRAINTS_JUJU_MAP[parts[0]]] = parts[1]
    return constraints


class NodeListView(PaginatedListView):

    context_object_name = "node_list"

    def get(self, request, *args, **kwargs):
        self.query = request.GET.get("query")
        self.query_error = None
        self.sort_by = request.GET.get("sort")
        self.sort_dir = request.GET.get("dir")

        return super(NodeListView, self).get(request, *args, **kwargs)

    def get_queryset(self):
        # Default sort - newest first, unless sorting params are
        # present. In addition, to ensure order consistency, when
        # sorting by non-unique fields (like status), we always
        # sort by the unique creation date as well
        if self.sort_by is not None:
            prefix = '-' if self.sort_dir == 'desc' else ''
            order_by = (prefix + self.sort_by, '-created')
        else:
            order_by = ('-created', )

        # Return the sorted node list
        nodes = Node.objects.get_nodes(
            user=self.request.user, prefetch_mac=True,
            perm=NODE_PERMISSION.VIEW,).order_by(*order_by)
        if self.query:
            try:
                return constrain_nodes(nodes, _parse_constraints(self.query))
            except InvalidConstraint as e:
                self.query_error = e
                return Node.objects.none()
        nodes = nodes.select_related('nodegroup')
        nodes = nodes.prefetch_related('nodegroup__nodegroupinterface_set')
        return nodes

    def _prepare_sort_links(self):
        """Returns 2 dicts, with sort fields as keys and
        links and CSS classes for the that field.
        """

        fields = ('hostname', 'status')
        # Build relative URLs for the links, just with the params
        links = {field: '?' for field in fields}
        classes = {field: 'sort-none' for field in fields}

        params = self.request.GET.copy()
        reverse_dir = 'asc' if self.sort_dir == 'desc' else 'desc'

        for field in fields:
            params['sort'] = field
            if field == self.sort_by:
                params['dir'] = reverse_dir
                classes[field] = 'sort-%s' % self.sort_dir
            else:
                params['dir'] = 'asc'

            links[field] += params.urlencode()

        return links, classes

    def get_context_data(self, **kwargs):
        context = super(NodeListView, self).get_context_data(**kwargs)
        context.update(get_longpoll_context())
        context["input_query"] = self.query
        context["input_query_error"] = self.query_error
        links, classes = self._prepare_sort_links()
        context["sort_links"] = links
        context["sort_classes"] = classes
        return context


def enlist_preseed_view(request):
    """View method to display the enlistment preseed."""
    return render_to_response(
        'maasserver/enlist_preseed.html',
        {'preseed': mark_safe(get_enlist_preseed())},
        context_instance=RequestContext(request))


class NodeViewMixin:
    """Mixin class used to fetch a node by system_id.

    The logged-in user must have View permission to access this page.
    """

    context_object_name = 'node'

    def get_object(self):
        system_id = self.kwargs.get('system_id', None)
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=self.request.user,
            perm=NODE_PERMISSION.VIEW)
        return node


class NodePreseedView(NodeViewMixin, DetailView):
    """View class to display a node's preseed."""

    template_name = 'maasserver/node_preseed.html'

    def get_context_data(self, **kwargs):
        context = super(NodePreseedView, self).get_context_data(**kwargs)
        node = self.get_object()
        # Display the preseed content exactly as generated by
        # `get_preseed`.  This will be rendered in a <pre> tag.
        context['preseed'] = mark_safe(get_preseed(node))
        context['is_commissioning'] = (
            node.status == NODE_STATUS.COMMISSIONING)
        return context


# Info message displayed on the node page for COMMISSIONING
# or READY nodes.
NODE_BOOT_INFO = mark_safe("""
You can boot this node using Avahi-enabled boot media or an adequately
configured dhcp server.  See
<a href="https://wiki.ubuntu.com/ServerTeam/MAAS/AvahiBoot">
https://wiki.ubuntu.com/ServerTeam/MAAS/AvahiBoot</a> for instructions.
""")


class NodeView(NodeViewMixin, UpdateView):
    """View class to display a node's information and buttons for the actions
    which can be performed on this node.
    """

    template_name = 'maasserver/node_view.html'

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
        return get_node_edit_form(self.request.user)

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


class MacAdd(CreateView):
    form_class = MACAddressForm
    template_name = 'maasserver/node_add_mac.html'

    def get_node(self):
        system_id = self.kwargs.get('system_id', None)
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=self.request.user,
            perm=NODE_PERMISSION.EDIT)
        return node

    def get_form_kwargs(self):
        kwargs = super(MacAdd, self).get_form_kwargs()
        kwargs['node'] = self.get_node()
        return kwargs

    def form_valid(self, form):
        res = super(MacAdd, self).form_valid(form)
        messages.info(self.request, "MAC address added.")
        return res

    def get_success_url(self):
        node = self.get_node()
        return reverse('node-edit', args=[node.system_id])

    def get_context_data(self, **kwargs):
        context = super(MacAdd, self).get_context_data(**kwargs)
        context.update({'node': self.get_node()})
        return context


class MacDelete(HelpfulDeleteView):

    template_name = 'maasserver/mac_confirm_delete.html'
    context_object_name = 'mac_to_delete'
    model = MACAddress

    def get_node(self):
        system_id = self.kwargs.get('system_id', None)
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=self.request.user,
            perm=NODE_PERMISSION.EDIT)
        return node

    def get_object(self):
        node = self.get_node()
        mac_address = self.kwargs.get('mac_address', None)
        return get_object_or_404(
            MACAddress, node=node, mac_address=mac_address)

    def get_next_url(self):
        node = self.get_node()
        return reverse('node-edit', args=[node.system_id])

    def name_object(self, obj):
        """See `HelpfulDeleteView`."""
        return "MAC address %s" % obj.mac_address
