# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Nodes views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'enlist_preseed_view',
    'MacAdd',
    'MacDelete',
    'NodeListView',
    'NodePreseedView',
    'NodeView',
    'NodeEdit',
    'prefetch_nodes_listing',
    ]

from urllib import urlencode

from django.conf import settings as django_settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import QueryDict
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
from django.views.generic.edit import (
    FormMixin,
    ProcessFormView,
    )
from lxml import etree
from maasserver import logger
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    )
from maasserver.exceptions import (
    MAASAPIException,
    NoRabbit,
    )
from maasserver.forms import (
    BulkNodeActionForm,
    get_action_form,
    get_node_edit_form,
    MACAddressForm,
    )
from maasserver.messages import messaging
from maasserver.models import (
    MACAddress,
    Node,
    Tag,
    )
from maasserver.models.nodeprobeddetails import get_single_probed_details
from maasserver.node_action import ACTIONS_DICT
from maasserver.node_constraint_filter_forms import (
    AcquireNodeForm,
    JUJU_ACQUIRE_FORM_FIELDS_MAPPING,
    )
from maasserver.preseed import (
    get_enlist_preseed,
    get_preseed,
    )
from maasserver.views import (
    HelpfulDeleteView,
    PaginatedListView,
    )
from provisioningserver.enum import POWER_TYPE
from provisioningserver.tags import merge_details_cleanly


def get_longpoll_context():
    if messaging is not None and django_settings.LONGPOLL_PATH is not None:
        try:
            return {
                'longpoll_queue': messaging.getQueue().name,
                'LONGPOLL_PATH': django_settings.LONGPOLL_PATH,
                }
        except NoRabbit as e:
            logger.warn("Could not connect to RabbitMQ: %s", e)
            return {}
    else:
        return {}


def _parse_constraints(query_string):
    """Turn query string from user into a QueryDict.

    This method parse the given query string and returns a QueryDict suitable
    to be passed to AcquireNodeForm().
    This is basically to mimic the way the juju behaves: any parameters with
    a value of 'any' will be ignored.
    """
    constraints = []
    for word in query_string.strip().split():
        parts = word.split("=", 1)
        if len(parts) != 2:
            # Empty constraint.
            constraints.append("%s=" % parts[0])
        elif parts[1] != "any":
            # 'any' constraint: discard it.
            constraints.append("%s=%s" % tuple(parts))
    return QueryDict('&'.join(constraints))


def message_from_form_stats(action, done, not_actionable, not_permitted):
    """Return a message suitable for user display from the given stats."""
    action_name = 'The action "%s"' % action.display_bulk
    # singular/plural messages.
    done_templates = [
        '%s was successfully performed on %d node.',
        '%s was successfully performed on %d nodes.'
    ]
    not_actionable_templates = [
        ('%s could not be performed on %d node because its '
         'state does not allow that action.'),
        ('%s could not be performed on %d nodes because their '
         'state does not allow that action.'),
    ]
    not_permitted_templates = [
        ('%s could not be performed on %d node because that '
         "action is not permitted on that node."),
        ('%s could not be performed on %d nodes because that '
         "action is not permitted on these nodes."),
    ]
    number_message = [
        (done, done_templates),
        (not_actionable, not_actionable_templates),
        (not_permitted, not_permitted_templates)]
    message = []
    for number, message_templates in number_message:
        singular, plural = message_templates
        if number != 0:
            message_template = singular if number == 1 else plural
            message.append(message_template % (action_name, number))
            # Override the action name so that only the first sentence will
            # contain the full name of the action.
            action_name = 'It'
    return ' '.join(message)


def prefetch_nodes_listing(nodes_query):
    """Prefetch any data needed to display a given query of nodes.

    :param nodes_query: A query set of nodes.
    :return: A version of `nodes_query` that prefetches any data needed for
        displaying these nodes as a listing.
    """
    return (
        nodes_query
        .prefetch_related('macaddress_set')
        .select_related('nodegroup')
        .prefetch_related('nodegroup__nodegroupinterface_set'))


class NodeListView(PaginatedListView, FormMixin, ProcessFormView):

    context_object_name = "node_list"
    form_class = BulkNodeActionForm
    sort_fields = ('hostname', 'status')

    def populate_modifiers(self, request):
        self.query = request.GET.get("query")
        self.query_error = None
        self.sort_by = request.GET.get("sort")
        self.sort_dir = request.GET.get("dir")

    def get(self, request, *args, **kwargs):
        """Handle a GET request."""
        self.populate_modifiers(request)
        return super(NodeListView, self).get(request, *args, **kwargs)

    def get_preserved_params(self):
        """List of GET parameters that need to be preserved by POST
        requests.

        These are sorting and search option we want a POST request to
        preserve so that the display after a POST request is similar
        to the display before the request."""
        return ["dir", "query", "page", "sort"]

    def get_preserved_query(self):
        params = {
            param: self.request.GET.get(param)
            for param in self.get_preserved_params()
            if self.request.GET.get(param) is not None}
        return urlencode(params)

    def get_next_url(self):
        return reverse('node-list') + "?" + self.get_preserved_query()

    def get_success_url(self):
        return self.get_next_url()

    def get_form_kwargs(self):
        kwargs = super(NodeListView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):
        """Handle a POST request."""
        self.populate_modifiers(request)
        return super(NodeListView, self).post(request, *args, **kwargs)

    def form_invalid(self, form):
        """Handle the view response when the form is invalid."""
        self.object_list = self.get_queryset()
        context = self.get_context_data(
            object_list=self.object_list,
            form=form)
        return self.render_to_response(context)

    def form_valid(self, form):
        """Handle the view response when the form is valid."""
        stats = form.save()
        action_class = ACTIONS_DICT[form.cleaned_data['action']]
        message = message_from_form_stats(action_class, *stats)
        messages.info(self.request, message)
        return super(NodeListView, self).form_valid(form)

    def _compose_sort_order(self):
        """Put together a tuple describing the sort order.

        The result can be passed to a node query's `order_by` method.
        Wherever two nodes are equal under the sorter order, creation date
        is used as a tie-breaker: newest node first.
        """
        if self.sort_by not in self.sort_fields:
            order_by = ()
        else:
            custom_order = self.sort_by
            if self.sort_dir == 'desc':
                custom_order = '-%s' % custom_order
            order_by = (custom_order, )

        return order_by + ('-created', )

    def _constrain_nodes(self, nodes_query):
        """Filter the given nodes query by user-specified constraints.

        If the specified constraints are invalid, this will set an error and
        return an empty query set.

        :param nodes_query: A query set of nodes.
        :return: A query set of nodes that returns a subset of `nodes_query`.
        """
        data = _parse_constraints(self.query)
        form = AcquireNodeForm.Strict(data=data)
        # Change the field names of the AcquireNodeForm object to
        # conform to Juju's naming.
        form.rename_fields(JUJU_ACQUIRE_FORM_FIELDS_MAPPING)
        if form.is_valid():
            return form.filter_nodes(nodes_query)
        else:
            self.query_error = ', '.join(
                ["%s: %s" % (field, ', '.join(errors))
                 for field, errors in form.errors.items()])
            return Node.objects.none()

    def get_queryset(self):
        nodes = Node.objects.get_nodes(
            user=self.request.user, perm=NODE_PERMISSION.VIEW)
        nodes = nodes.order_by(*self._compose_sort_order())
        if self.query:
            nodes = self._constrain_nodes(nodes)
        return prefetch_nodes_listing(nodes)

    def _prepare_sort_links(self):
        """Returns 2 dicts, with sort fields as keys and
        links and CSS classes for the that field.
        """

        # Build relative URLs for the links, just with the params
        links = {field: '?' for field in self.sort_fields}
        classes = {field: 'sort-none' for field in self.sort_fields}

        params = self.request.GET.copy()
        reverse_dir = 'asc' if self.sort_dir == 'desc' else 'desc'

        for field in self.sort_fields:
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
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context["preserved_query"] = self.get_preserved_query()
        context["form"] = form
        context["input_query"] = self.query
        context["input_query_error"] = self.query_error
        links, classes = self._prepare_sort_links()
        context["sort_links"] = links
        context["sort_classes"] = classes
        return context


def enlist_preseed_view(request):
    """View method to display the enlistment preseed."""
    warning_message = (
        "The URL mentioned in the following enlistment preseed will "
        "be different depending on which cluster controller is "
        "responsible for the enlisting node.  The URL shown here is for "
        "nodes handled by the cluster controller located in the region "
        "controller's network."
        )
    context = RequestContext(request, {'warning_message': warning_message})
    return render_to_response(
        'maasserver/enlist_preseed.html',
        {'preseed': mark_safe(get_enlist_preseed())},
        context_instance=context)


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
configured DHCP server.  See
<a href="https://maas.ubuntu.com/docs/nodes.html"
>https://maas.ubuntu.com/docs/nodes.html</a> for instructions.
""")


NO_POWER_SET = mark_safe("""
This node does not have a power type set and MAAS will be unable to
control it. Click 'Edit node' and set one.
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
        if node.power_type == POWER_TYPE.DEFAULT:
            messages.error(self.request, NO_POWER_SET)
        context['error_text'] = (
            node.error if node.status == NODE_STATUS.FAILED_TESTS else None)
        context['status_text'] = (
            node.error if node.status != NODE_STATUS.FAILED_TESTS else None)
        kernel_opts = node.get_effective_kernel_options()
        context['kernel_opts'] = {
            'is_global': kernel_opts[0] is None,
            'is_tag': isinstance(kernel_opts[0], Tag),
            'tag': kernel_opts[0],
            'value': kernel_opts[1]
            }
        # Produce a "clean" composite details document.
        probed_details = merge_details_cleanly(
            get_single_probed_details(node.system_id))
        # We check here if there's something to show instead of after
        # the call to get_single_probed_details() because here the
        # details will be guaranteed well-formed.
        if len(probed_details.xpath('/*/*')) == 0:
            context["probed_details"] = None
        else:
            context["probed_details"] = etree.tostring(
                probed_details, encoding=unicode, pretty_print=True)
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
