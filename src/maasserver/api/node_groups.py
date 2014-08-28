# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `NodeGroup`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'check_nodegroup_access',
    'NodeGroupHandler',
    'NodeGroupsHandler',
    ]

import httplib
from urlparse import urlparse

import bson
from celery.app import app_or_default
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from formencode import validators
from maasserver.api.logger import maaslog
from maasserver.api.support import (
    admin_method,
    AnonymousOperationsHandler,
    operation,
    OperationsHandler,
    )
from maasserver.api.utils import (
    extract_oauth_key,
    get_list_from_dict_or_multidict,
    get_mandatory_param,
    get_optional_param,
    )
from maasserver.clusterrpc.power_parameters import (
    get_all_power_types_from_clusters,
    )
from maasserver.enum import NODEGROUP_STATUS
from maasserver.exceptions import Unauthorized
from maasserver.forms import (
    DownloadProgressForm,
    NodeGroupDefineForm,
    NodeGroupEdit,
    )
from maasserver.models import (
    DHCPLease,
    MACAddress,
    Network,
    Node,
    NodeGroup,
    )
from maasserver.models.nodeprobeddetails import get_probed_details
from maasserver.utils import (
    build_absolute_uri,
    get_local_cluster_UUID,
    )
from maasserver.utils.orm import get_one
import netaddr
import simplejson as json


DISPLAYED_NODEGROUP_FIELDS = ('uuid', 'status', 'name', 'cluster_name')


def register_nodegroup(request, uuid):
    """Register a new nodegroup.

    If the master has not been configured yet, this nodegroup becomes the
    master.  In that situation, if the uuid is also the one configured locally
    (meaning that the cluster controller is running on the same host as this
    region controller), the new master is also automatically accepted.
    """
    master = NodeGroup.objects.ensure_master()

    # Has the master been configured yet?
    if master.uuid in ('master', ''):
        # No, the master is not yet configured.  No actual cluster
        # controllers have registered yet.  All we have is the
        # default placeholder.  We let the cluster controller that's
        # making this request take the master's place.
        update_instance = master
        local_uuid = get_local_cluster_UUID()
        is_local_cluster = (
            local_uuid is not None and
            uuid == local_uuid)
        if is_local_cluster:
            # It's the cluster controller that's running locally.
            # Auto-accept it.
            status = NODEGROUP_STATUS.ACCEPTED
        else:
            # It's a non-local cluster controller.  Keep it pending.
            status = NODEGROUP_STATUS.PENDING
    else:
        # It's a new regular cluster.  Create it, and keep it pending.
        update_instance = None
        status = NODEGROUP_STATUS.PENDING

    form = NodeGroupDefineForm(
        data=request.data, status=status, instance=update_instance)

    if not form.is_valid():
        raise ValidationError(form.errors)

    cluster = form.save()
    maaslog.info("New cluster controller registered: %s", cluster.name)
    return cluster


def get_celery_credentials():
    """Return the credentials needed to connect to the broker."""
    celery_conf = app_or_default().conf
    return {
        'BROKER_URL': celery_conf.BROKER_URL,
    }


def compose_nodegroup_register_response(nodegroup, already_existed):
    """Return the right HTTP response to a `register` request.

    The response is based on the status of the `nodegroup` after registration,
    and whether it had already been registered before the call.

    If the nodegroup was accepted, this returns the cluster worker's Celery
    credentials.
    """
    if nodegroup.status == NODEGROUP_STATUS.ACCEPTED:
        return get_celery_credentials()
    elif nodegroup.status == NODEGROUP_STATUS.REJECTED:
        raise PermissionDenied('Rejected cluster.')
    elif nodegroup.status == NODEGROUP_STATUS.PENDING:
        if already_existed:
            message = "Awaiting admin approval."
        else:
            message = "Cluster registered.  Awaiting admin approval."
        return HttpResponse(message, status=httplib.ACCEPTED)
    else:
        raise AssertionError("Unknown nodegroup status: %s", nodegroup.status)


class AnonNodeGroupsHandler(AnonymousOperationsHandler):
    """Anonymous access to NodeGroups."""
    create = read = update = delete = None
    fields = DISPLAYED_NODEGROUP_FIELDS

    @operation(idempotent=True)
    def list(self, request):
        """List of node groups."""
        return NodeGroup.objects.all()

    @classmethod
    def resource_uri(cls):
        return ('nodegroups_handler', [])

    @operation(idempotent=False)
    def refresh_workers(self, request):
        """Request an update of all node groups' configurations.

        This sends each node-group worker an update of its API credentials,
        OMAPI key, node-group name, and so on.

        Anyone can request this (for example, a bootstrapping worker that
        does not know its node-group name or API credentials yet) but the
        information will be sent only to the known workers.
        """
        NodeGroup.objects.refresh_workers()
        return HttpResponse("Sending worker refresh.", status=httplib.OK)

    @operation(idempotent=False)
    def register(self, request):
        """Register a new cluster controller.

        This method will use HTTP return codes to indicate the success of the
        call:

        - 200 (OK): the cluster controller has been accepted.  The response
          will contain the RabbitMQ credentials in JSON format, e.g.:
          '{"BROKER_URL" = "amqp://guest:guest@localhost:5672//"}'
        - 202 (Accepted): the cluster controller has been registered.  It is
          now pending acceptance by an administrator.  Please try again later.
        - 403 (Forbidden): this cluster controller has been rejected.

        :param uuid: The cluster's UUID.
        :type name: unicode
        :param name: The cluster's name.
        :type name: unicode
        :param interfaces: The cluster controller's network interfaces.
        :type interfaces: JSON string containing a list of dictionaries with
            the data to initialize the interfaces.
            e.g.: '[{"ip_range_high": "192.168.168.254",
            "ip_range_low": "192.168.168.1", "broadcast_ip":
            "192.168.168.255", "ip": "192.168.168.18", "subnet_mask":
            "255.255.255.0", "router_ip": "192.168.168.1", "interface":
            "eth0"}]'
        """
        uuid = get_mandatory_param(request.data, 'uuid')
        nodegroup = get_one(NodeGroup.objects.filter(uuid=uuid))
        already_existed = (nodegroup is not None)
        if already_existed:
            if nodegroup.status == NODEGROUP_STATUS.ACCEPTED:
                # This cluster controller has been accepted.  Use the
                # information in the request to update the MAAS URL we will
                # send it from now on.
                update_nodegroup_maas_url(nodegroup, request)
        else:
            nodegroup = register_nodegroup(request, uuid)

        return compose_nodegroup_register_response(nodegroup, already_existed)


def update_nodegroup_maas_url(nodegroup, request):
    """Update `nodegroup.maas_url` from the given `request`.

    Only update `nodegroup.maas_url` if the hostname part is not 'localhost'
    (i.e. the default value used when the master nodegroup connects).
    """
    path = request.META["SCRIPT_NAME"]
    maas_url = build_absolute_uri(request, path)
    server_host = urlparse(maas_url).hostname
    if server_host != 'localhost':
        nodegroup.maas_url = maas_url
        nodegroup.save()


def update_mac_cluster_interfaces(leases, cluster):
    """Calculate and store which interface a MAC is attached to."""
    interface_ranges = {}
    # Only consider configured interfaces.
    interfaces = (
        cluster.nodegroupinterface_set
        .exclude(ip_range_low__isnull=True)
        .exclude(ip_range_high__isnull=True)
    )
    for interface in interfaces:
        ip_range = netaddr.IPRange(
            interface.ip_range_low, interface.ip_range_high)
        if interface.static_ip_range_low and interface.static_ip_range_high:
            static_range = netaddr.IPRange(
                interface.static_ip_range_low, interface.static_ip_range_high)
        else:
            static_range = []
        interface_ranges[interface] = (ip_range, static_range)
    for ip, mac in leases.items():
        try:
            mac_address = MACAddress.objects.get(mac_address=mac)
        except MACAddress.DoesNotExist:
            # Silently ignore MAC addresses that we don't know about.
            continue
        for interface, (ip_range, static_range) in interface_ranges.items():
            ipaddress = netaddr.IPAddress(ip)
            if ipaddress in ip_range or ipaddress in static_range:
                mac_address.cluster_interface = interface
                mac_address.save()

                # Locate the Network to which this MAC belongs.
                ipnetwork = interface.network
                if ipnetwork is not None:
                    try:
                        network = Network.objects.get(ip=ipnetwork.ip.format())
                        network.macaddress_set.add(mac_address)
                    except Network.DoesNotExist:
                        pass

                # Cheap optimisation. No other interfaces will match, so
                # break out of the loop.
                break


class NodeGroupsHandler(OperationsHandler):
    """Manage the collection of all the nodegroups in this MAAS."""

    api_doc_section_name = "Nodegroups"
    anonymous = AnonNodeGroupsHandler
    create = read = update = delete = None
    fields = DISPLAYED_NODEGROUP_FIELDS

    @operation(idempotent=True)
    def list(self, request):
        """List nodegroups."""
        return NodeGroup.objects.all()

    @admin_method
    @operation(idempotent=False)
    def accept(self, request):
        """Accept nodegroup enlistment(s).

        :param uuid: The UUID (or list of UUIDs) of the nodegroup(s) to accept.
        :type name: unicode (or list of unicodes)

        This method is reserved to admin users.
        """
        uuids = request.data.getlist('uuid')
        for uuid in uuids:
            nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
            nodegroup.accept()
        return HttpResponse("Nodegroup(s) accepted.", status=httplib.OK)

    @admin_method
    @operation(idempotent=False)
    def import_boot_images(self, request):
        """Import the boot images on all the accepted cluster controllers."""
        NodeGroup.objects.import_boot_images_on_accepted_clusters()
        return HttpResponse(
            "Import of boot images started on all cluster controllers",
            status=httplib.OK)

    @operation(idempotent=True)
    def describe_power_types(self, request):
        """Query all the cluster controllers for power information.

        :return: a list of dicts that describe the power types in this format.
        """
        return get_all_power_types_from_clusters()

    @admin_method
    @operation(idempotent=False)
    def reject(self, request):
        """Reject nodegroup enlistment(s).

        :param uuid: The UUID (or list of UUIDs) of the nodegroup(s) to reject.
        :type name: unicode (or list of unicodes)

        This method is reserved to admin users.
        """
        uuids = request.data.getlist('uuid')
        for uuid in uuids:
            nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
            nodegroup.reject()
        return HttpResponse("Nodegroup(s) rejected.", status=httplib.OK)

    @classmethod
    def resource_uri(cls):
        return ('nodegroups_handler', [])


def check_nodegroup_access(request, nodegroup):
    """Validate API access by worker for `nodegroup`.

    This supports a nodegroup worker accessing its nodegroup object on
    the API.  If the request is done by anyone but the worker for this
    particular nodegroup, the function raises :class:`PermissionDenied`.
    """
    try:
        key = extract_oauth_key(request)
    except Unauthorized as e:
        raise PermissionDenied(unicode(e))

    if key != nodegroup.api_key:
        raise PermissionDenied(
            "Only allowed for the %r worker." % nodegroup.name)


class NodeGroupHandler(OperationsHandler):
    """Manage a NodeGroup.

    NodeGroup is the internal name for a cluster.

    The NodeGroup is identified by its UUID, a random identifier that looks
    something like:

        5977f6ab-9160-4352-b4db-d71a99066c4f

    Each NodeGroup has its own uuid.
    """
    api_doc_section_name = "Nodegroup"

    create = delete = None
    fields = DISPLAYED_NODEGROUP_FIELDS

    def read(self, request, uuid):
        """GET a node group."""
        return get_object_or_404(NodeGroup, uuid=uuid)

    @classmethod
    def resource_uri(cls, nodegroup=None):
        if nodegroup is None:
            uuid = 'uuid'
        else:
            uuid = nodegroup.uuid
        return ('nodegroup_handler', [uuid])

    @admin_method
    def update(self, request, uuid):
        """Update a specific cluster.

        :param name: The new DNS name for this cluster.
        :type name: unicode
        :param cluster_name: The new name for this cluster.
        :type cluster_name: unicode
        :param status: The new status for this cluster (see
            vocabulary `NODEGROUP_STATUS`).
        :type status: int
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        form = NodeGroupEdit(instance=nodegroup, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise ValidationError(form.errors)

    @operation(idempotent=False)
    def update_leases(self, request, uuid):
        """Submit latest state of DHCP leases within the cluster.

        The cluster controller calls this periodically to tell the region
        controller about the IP addresses it manages.
        """
        leases = get_mandatory_param(request.data, 'leases')
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        check_nodegroup_access(request, nodegroup)
        leases = json.loads(leases)
        DHCPLease.objects.update_leases(nodegroup, leases)
        update_mac_cluster_interfaces(leases, nodegroup)
        return HttpResponse("Leases updated.", status=httplib.OK)

    @admin_method
    @operation(idempotent=False)
    def import_boot_images(self, request, uuid):
        """Import the pxe files on this cluster controller."""
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        nodegroup.import_boot_images()
        return HttpResponse(
            "Import of boot images started on cluster %r" % nodegroup.uuid,
            status=httplib.OK)

    @operation(idempotent=True)
    def list_nodes(self, request, uuid):
        """Get the list of node ids that are part of this group."""
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        if not request.user.is_superuser:
            check_nodegroup_access(request, nodegroup)
        nodes = Node.objects.filter(nodegroup=nodegroup).only('system_id')
        return [node.system_id for node in nodes]

    # details is actually idempotent, however:
    # a) We expect to get a list of system_ids which is quite long (~100 ids,
    #    each 40 bytes, is 4000 bytes), which is a bit too long for a URL.
    # b) MAASClient.get() just uses urlencode(params) but urlencode ends up
    #    just stringifying the list and encoding that, which transforms the
    #    list of ids into something unusable. .post() does the right thing.
    @operation(idempotent=False)
    def details(self, request, uuid):
        """Obtain various system details for each node specified.

        For example, LLDP and ``lshw`` XML dumps.

        Returns a ``{system_id: {detail_type: xml, ...}, ...}`` map,
        where ``detail_type`` is something like "lldp" or "lshw".

        :param system_ids: System ids of nodes for which to get system details.

        Note that this is returned as BSON and not JSON. This is for
        efficiency, but mainly because JSON can't do binary content
        without applying additional encoding like base-64.

        For security purposes:

        a) Requests are only fulfilled for the worker assigned to the
           nodegroup.
        b) Requests for nodes that are not part of the nodegroup are
           just ignored.

        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        if not request.user.is_superuser:
            check_nodegroup_access(request, nodegroup)
        system_ids = get_list_from_dict_or_multidict(
            request.data, 'system_ids', [])
        # Filter out system IDs that are not in this nodegroup.
        system_ids = Node.objects.filter(
            system_id__in=system_ids, nodegroup=nodegroup)
        # Unwrap the values_list.
        system_ids = {
            system_id for (system_id,) in
            system_ids.values_list('system_id')
        }
        # Obtain details and prepare for BSON encoding.
        details = get_probed_details(system_ids)
        for detail in details.itervalues():
            for name, value in detail.iteritems():
                if value is not None:
                    detail[name] = bson.Binary(value)
        return HttpResponse(
            bson.BSON.encode(details),
            # Not sure what media type to use here.
            content_type='application/bson')

    @operation(idempotent=False)
    def report_download_progress(self, request, uuid):
        """Report progress of a download.

        Cluster controllers can call this to update the region controller on
        file downloads they need to perform, such as kernels and initrd files.
        This gives the administrator insight into what downloads are in
        progress, how well downloads are going, and what failures may have
        occurred.

        A file is identified by an arbitrary name, which must be consistent.
        It could be a URL, or a filesystem path, or even a symbolic name that
        the cluster controller makes up.  A cluster controller can download
        the same file many times over, but not simultaneously.

        Before downloading a file, a cluster controller first reports progress
        without the `bytes_downloaded` parameter.  It may optionally report
        progress while downloading, passing the number of bytes downloaded
        so far.  Finally, if the download succeeded, it should report one final
        time with the full number of bytes downloaded.

        If the download fails, the cluster controller should report progress
        with an error string (and either the number of bytes that were
        successfully downloaded, or zero).

        Progress reports should include the file's size, if known.  The final
        report after a successful download must include the size.

        :param filename: Arbitrary identifier for the file being downloaded.
        :type filename: unicode
        :param size: Optional size of the file, in bytes.  Must be passed at
            least once, though it can still be passed on subsequent calls.  If
            file size is not known, pass it at the end when reporting
            successful completion.  Do not change the size once given.
        :param bytes_downloaded: Number of bytes that have been successfully
            downloaded.  Cannot exceed `size`, if known.  This parameter must
            be omitted from the initial progress report before download starts,
            and must be included for all subsequent progress reports for that
            download.
        :type bytes_downloaded: int
        :param error: Optional error string.  A download that has submitted an
            error with its last progress report is considered to have failed.
        :type error: unicode
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        check_nodegroup_access(request, nodegroup)
        filename = get_mandatory_param(request.data, 'filename')
        bytes_downloaded = request.data.get('bytes_downloaded', None)

        download = DownloadProgressForm.get_download(
            nodegroup, filename, bytes_downloaded)

        if 'size' not in request.data:
            # No size given.  If one was specified previously, use that.
            request.data['size'] = download.size

        form = DownloadProgressForm(data=request.data, instance=download)
        if not form.is_valid():
            raise ValidationError(form.errors)
        form.save()

        return HttpResponse(status=httplib.OK)

    @admin_method
    @operation(idempotent=False)
    def probe_and_enlist_hardware(self, request, uuid):
        """Add special hardware types.

        :param model: The type of special hardware, 'seamicro15k' and
            'virsh' is supported.
        :type model: unicode

        The following are only required if you are probing a seamicro15k:

        :param mac: The MAC of the seamicro15k chassis.
        :type mac: unicode
        :param username: The username for the chassis.
        :type username: unicode
        :param password: The password for the chassis.
        :type password: unicode

        The following are optional if you are probing a seamicro15k:

        :param power_control: The power_control to use, either ipmi (default)
            or restapi.
        :type power_control: unicode

        The following are only required if you are probing a virsh:

        :param power_address: The connection string to virsh.
        :type power_address: unicode

        The following are optional if you are probing a virsh:

        :param power_pass: The password to use, when qemu+ssh is given as a
            connection string and ssh key authentication is not being used.
        :type power_pass: unicode
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)

        model = get_mandatory_param(request.data, 'model')
        if model == 'seamicro15k':
            mac = get_mandatory_param(request.data, 'mac')
            username = get_mandatory_param(request.data, 'username')
            password = get_mandatory_param(request.data, 'password')
            power_control = get_optional_param(
                request.data, 'power_control', default='ipmi',
                validator=validators.OneOf(['ipmi', 'restapi', 'restapi2']))

            nodegroup.add_seamicro15k(
                mac, username, password, power_control=power_control)
        elif model == 'powerkvm' or model == 'virsh':
            poweraddr = get_mandatory_param(request.data, 'power_address')
            password = get_optional_param(
                request.data, 'power_pass', default=None)

            nodegroup.add_virsh(poweraddr, password=password)
        else:
            return HttpResponse(status=httplib.BAD_REQUEST)

        return HttpResponse(status=httplib.OK)

    @admin_method
    @operation(idempotent=False)
    def probe_and_enlist_ucsm(self, request, uuid):
        """Add the nodes from a Cisco UCS Manager.

        :param : The URL of the UCS Manager API.
        :type url: unicode
        :param username: The username for the API.
        :type username: unicode
        :param password: The password for the API.
        :type password: unicode

        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)

        url = get_mandatory_param(request.data, 'url')
        username = get_mandatory_param(request.data, 'username')
        password = get_mandatory_param(request.data, 'password')

        nodegroup.enlist_nodes_from_ucsm(url, username, password)

        return HttpResponse(status=httplib.OK)

    @admin_method
    @operation(idempotent=False)
    def probe_and_enlist_mscm(self, request, uuid):
        """Add the nodes from a Moonshot HP iLO Chassis Manager (MSCM).

        :param host: IP Address for the MSCM.
        :type host: unicode
        :param username: The username for the MSCM.
        :type username: unicode
        :param password: The password for the MSCM.
        :type password: unicode

        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)

        host = get_mandatory_param(request.data, 'host')
        username = get_mandatory_param(request.data, 'username')
        password = get_mandatory_param(request.data, 'password')

        nodegroup.enlist_nodes_from_mscm(host, username, password)

        return HttpResponse(status=httplib.OK)
