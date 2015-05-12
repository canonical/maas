# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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
    'NodeDelete',
    'NodeEventListView',
    'NodePreseedView',
    'NodeView',
    'NodeEdit',
    'prefetch_nodes_listing',
]

from cgi import escape
import json
import logging
import re
from textwrap import dedent

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import (
    get_object_or_404,
    render_to_response,
)
from django.template import (
    loader,
    RequestContext,
)
from django.utils.safestring import mark_safe
from django.views.generic import (
    CreateView,
    DetailView,
    UpdateView,
)
from lxml import etree
from maasserver.clusterrpc.power_parameters import get_power_types
from maasserver.enum import (
    NODE_BOOT,
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
)
from maasserver.exceptions import MAASAPIException
from maasserver.forms import (
    get_action_form,
    get_node_edit_form,
    MACAddressForm,
)
from maasserver.models import (
    MACAddress,
    Node,
    StaticIPAddress,
    Tag,
)
from maasserver.models.config import Config
from maasserver.models.event import Event
from maasserver.models.nodeprobeddetails import get_single_probed_details
from maasserver.preseed import (
    get_enlist_preseed,
    get_preseed,
    OS_WITH_IPv6_SUPPORT,
)
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils.converters import XMLToYAML
from maasserver.views import (
    HelpfulDeleteView,
    PaginatedListView,
)
from metadataserver.enum import RESULT_TYPE
from metadataserver.models import NodeResult
from netaddr import IPAddress
from provisioningserver.tags import merge_details_cleanly


def message_from_form_stats(action, done, not_actionable, not_permitted):
    """Return a message suitable for user display from the given stats."""
    action_name = 'The action "%s"' % action.display
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
    for index, (number, message_templates) in enumerate(number_message):
        singular, plural = message_templates
        if number != 0:
            message_template = singular if number == 1 else plural
            message.append(message_template % (action_name, number))
            # Override the action name so that only the first sentence will
            # contain the full name of the action.
            action_name = 'It'
            level = index
    return ' '.join(message), ('info', 'warning', 'error')[level]


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
        .prefetch_related('nodegroup__nodegroupinterface_set')
        .prefetch_related('zone'))


def generate_js_power_types(nodegroup=None):
    """Return a JavaScript definition of supported power-type choices.

    Produces an array of power-type identifiers, starting with the opening
    bracket and ending with the closing bracket, without line breaks on either
    end.  Entries are one per line, sorted lexicographically.
    """
    if nodegroup is not None:
        nodegroup = [nodegroup]
    power_types = get_power_types(nodegroup, ignore_errors=True)
    names = ['"%s"' % power_type for power_type in sorted(power_types)]
    return mark_safe("[\n%s\n]" % ',\n'.join(names))


def node_to_dict(node, event_log_count=0):
    """Convert `Node` to a dictionary.

    :param event_log_count: Number of entries from the event log to add to
        the dictionary.
    """
    if node.owner is None:
        owner = ""
    else:
        owner = '%s' % node.owner
    pxe_mac = node.get_pxe_mac()
    node_dict = dict(
        id=node.id,
        system_id=node.system_id,
        url=reverse('node-view', args=[node.system_id]),
        hostname=node.hostname,
        architecture=node.architecture,
        fqdn=node.fqdn,
        status=node.display_status(),
        owner=owner,
        cpu_count=node.cpu_count,
        memory=node.display_memory(),
        storage=node.display_storage(),
        power_state=node.power_state,
        zone=node.zone.name,
        zone_url=reverse('zone-view', args=[node.zone.name]),
        mac=None if pxe_mac is None else pxe_mac.mac_address.get_raw(),
        vendor=node.get_pxe_mac_vendor(),
        macs=[mac.mac_address.get_raw() for mac in node.get_extra_macs()],
    )
    if event_log_count != 0:
        # Add event information to the generated node dictionary. We exclude
        # debug after we calculate the count, so we show the correct total
        # number of events.
        node_events = Event.objects.filter(node=node)
        total_num_events = node_events.count()
        non_debug_events = node_events.exclude(
            type__level=logging.DEBUG).order_by('-id')
        if event_log_count > 0:
            # Limit the number of events.
            events = non_debug_events.all()[:event_log_count]
            displayed_events_count = len(events)
        node_dict['events'] = dict(
            total=total_num_events,
            count=displayed_events_count,
            events=[event_to_dict(event) for event in events],
            more_url=reverse('node-event-list-view', args=[node.system_id]),
        )
    return node_dict


def event_to_dict(event):
    """Convert `Event` to a dictionary."""
    return dict(
        node=event.node.system_id,
        hostname=event.node.hostname,
        id=event.id,
        level=event.type.level_str,
        created=event.created.strftime('%a, %d %b. %Y %H:%M:%S'),
        type=event.type.description,
        description=event.description
    )


def convert_query_status(value):
    """Convert the given value into a list of status integers."""
    value = value.lower()
    ids = []
    for status_id, status_text in NODE_STATUS_CHOICES_DICT.items():
        status_text = status_text.lower()
        if value in status_text:
            ids.append(status_id)
    if len(ids) == 0:
        return None
    return ids


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
    try:
        preseed = get_enlist_preseed()
    except NameError as e:
        preseed = "ERROR RENDERING PRESEED\n" + unicode(e)
    return render_to_response(
        'maasserver/enlist_preseed.html',
        {'preseed': mark_safe(preseed)},
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
        try:
            preseed = get_preseed(node)
        except NameError as e:
            preseed = "ERROR RENDERING PRESEED\n" + unicode(e)
        context['preseed'] = mark_safe(preseed)
        context['is_commissioning'] = (
            node.status == NODE_STATUS.COMMISSIONING)
        return context


# Info message displayed on the node page for COMMISSIONING
# or READY nodes.
NODE_BOOT_INFO = mark_safe("""
You can boot this node using an adequately
configured DHCP server.  See
<a href="https://maas.ubuntu.com/docs/nodes.html"
>https://maas.ubuntu.com/docs/nodes.html</a> for instructions.
""")


NO_POWER_SET = mark_safe("""
This node does not have a power type set and MAAS will be unable to
control it. Click 'Edit node' and set one.
""")


THIRD_PARTY_DRIVERS_NOTICE = dedent("""
    Third party drivers may be used when booting or installing nodes.
    These may be proprietary and closed-source.
    """)


THIRD_PARTY_DRIVERS_ADMIN_NOTICE = dedent("""
    The installation of third party drivers can be disabled on the <a
    href="%s#third_party_drivers">settings</a> page.
    """)

UNCONFIGURED_IPS_NOTICE = dedent("""
    Automatic configuration of IPv6 addresses is currently only supported on
    Ubuntu, using the fast installer.  To activate the IPv6 address(es) shown
    here, configure them in the installed operating system.
    """)


def construct_third_party_drivers_notice(user_is_admin):
    """Build and return the notice about third party drivers.

    If `user_is_admin` is True, a link to the settings page will be
    included in the message.

    :param user_is_admin: True if the user is an administrator, False
        otherwise.
    """
    if user_is_admin:
        return mark_safe(
            THIRD_PARTY_DRIVERS_NOTICE +
            THIRD_PARTY_DRIVERS_ADMIN_NOTICE %
            escape(reverse("settings"), quote=True))
    else:
        return mark_safe(THIRD_PARTY_DRIVERS_NOTICE)


class NodeView(NodeViewMixin, UpdateView):
    """View class to display a node's information and buttons for the actions
    which can be performed on this node.
    """

    template_name = 'maasserver/node_view.html'

    def get_form_class(self):
        return get_action_form(self.request.user, self.request)

    # The number of events shown on the node view page.
    number_of_events_shown = 5

    def get(self, request, *args, **kwargs):
        """Handle a GET request."""
        if request.is_ajax():
            return self.handle_ajax_request(request, *args, **kwargs)
        return super(NodeView, self).get(request, *args, **kwargs)

    def warn_unconfigured_ip_addresses(self, node):
        """Should the UI warn about unconfigured IPv6 addresses on the node?

        Static IPv6 addresses are configured on the node using Curtin.  But
        this is not yet supported for all operating systems and installers.
        If a node has IPv6 addresses assigned but is not being deployed in a
        way that supports configuring them, the node page should show a warning
        to say that the user will need to configure the node to use those
        addresses.

        :return: Bool: should the UI show this warning?
        """
        supported_os = (node.get_osystem() in OS_WITH_IPv6_SUPPORT)
        if supported_os and node.boot_type == NODE_BOOT.FASTPATH:
            # MAAS knows how to configure IPv6 addresses on an Ubuntu node
            # installed with the fast installer.  No warning needed.
            return False
        # For other installs, we need the warning if and only if the node has
        # static IPv6 addresses.
        static_ips = StaticIPAddress.objects.filter(macaddress__node=node)
        return any(
            IPAddress(static_ip.ip).version == 6
            for static_ip in static_ips)

    def get_context_data(self, **kwargs):
        context = super(NodeView, self).get_context_data(**kwargs)
        node = self.get_object()
        context['can_edit'] = self.request.user.has_perm(
            NODE_PERMISSION.EDIT, node)
        if node.status in (NODE_STATUS.COMMISSIONING, NODE_STATUS.READY):
            messages.info(self.request, NODE_BOOT_INFO)
        if node.power_type == '':
            messages.error(self.request, NO_POWER_SET)
        if self.warn_unconfigured_ip_addresses(node):
            messages.warning(self.request, UNCONFIGURED_IPS_NOTICE)
            context['unconfigured_ips_warning'] = UNCONFIGURED_IPS_NOTICE

        context['error_text'] = (
            node.error if node.status == NODE_STATUS.FAILED_COMMISSIONING
            else None)
        context['status_text'] = (
            node.error if node.status != NODE_STATUS.FAILED_COMMISSIONING
            else None)
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
            context['probed_details_xml'] = None
            context['probed_details_yaml'] = None
        else:
            context['probed_details_xml'] = etree.tostring(
                probed_details, encoding=unicode, pretty_print=True)
            context['probed_details_yaml'] = XMLToYAML(
                etree.tostring(
                    probed_details, encoding=unicode,
                    pretty_print=True)).convert()

        commissioning_results = NodeResult.objects.filter(
            node=node, result_type=RESULT_TYPE.COMMISSIONING).count()
        context['nodecommissionresults'] = commissioning_results

        installation_results = NodeResult.objects.filter(
            node=node, result_type=RESULT_TYPE.INSTALLATION)
        if len(installation_results) > 1:
            for result in installation_results:
                result.name = re.sub('[_.]', ' ', result.name)
            context['nodeinstallresults'] = installation_results
        elif len(installation_results) == 1:
            installation_results[0].name = "install log"
            context['nodeinstallresults'] = installation_results

        context['third_party_drivers_enabled'] = Config.objects.get_config(
            'enable_third_party_drivers')
        context['drivers'] = get_third_party_driver(node)

        event_list = (
            Event.objects.filter(node=self.get_object())
            .exclude(type__level=logging.DEBUG)
            .order_by('-id')[:self.number_of_events_shown])
        context['event_list'] = event_list
        context['event_count'] = Event.objects.filter(
            node=self.get_object()).count()

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

    def render_node_actions(self, request):
        """Render the HTML for all the available node actions."""
        template = loader.get_template('maasserver/node_actions.html')
        self.object = self.get_object()
        context = {
            'node': self.object,
            'can_edit': self.request.user.has_perm(
                NODE_PERMISSION.EDIT, self.object),
            'form': self.get_form(self.get_form_class()),
        }
        return template.render(RequestContext(request, context))

    def handle_ajax_request(self, request, *args, **kwargs):
        """JSON response to update the node view."""
        node = self.get_object()
        node = node_to_dict(
            node, event_log_count=self.number_of_events_shown)
        node['action_view'] = self.render_node_actions(request)
        return HttpResponse(json.dumps(node), mimetype='application/json')


class NodeEventListView(NodeViewMixin, PaginatedListView):

    context_object_name = "event_list"

    template_name = "maasserver/node_event_list.html"

    def get_queryset(self):
        return Event.objects.filter(
            node=self.get_object()).order_by('-id')

    def get_context_data(self, **kwargs):
        context = super(NodeEventListView, self).get_context_data(**kwargs)
        node = self.get_object()
        context['node'] = node
        return context


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

    def get_has_owner(self):
        node = self.get_object()
        if node is None or node.owner is None:
            return mark_safe("false")
        return mark_safe("true")

    def get_form_kwargs(self):
        # This is here so the request can be passed to the form. The
        # form needs it because it sets error messages for the UI.
        kwargs = super(NodeEdit, self).get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['ui_submission'] = True
        return kwargs

    def get_success_url(self):
        return reverse('node-view', args=[self.get_object().system_id])

    def get_context_data(self, **kwargs):
        context = super(NodeEdit, self).get_context_data(**kwargs)
        context['power_types'] = generate_js_power_types(
            self.get_object().nodegroup)
        # 'os_release' lets us know if we should render the `OS`
        # and `Release` choice fields in the UI.
        context['os_release'] = self.get_has_owner()
        return context


class NodeDelete(HelpfulDeleteView):

    template_name = 'maasserver/node_confirm_delete.html'
    context_object_name = 'node_to_delete'
    model = Node

    def get_object(self):
        system_id = self.kwargs.get('system_id', None)
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=self.request.user,
            perm=NODE_PERMISSION.ADMIN)
        return node

    def get_next_url(self):
        return reverse('index') + "#/nodes"

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
