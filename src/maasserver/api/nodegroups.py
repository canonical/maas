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

import bson
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from formencode import validators
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
from maasserver.exceptions import (
    MAASAPIValidationError,
    Unauthorized,
    )
from maasserver.forms import (
    DownloadProgressForm,
    NodeGroupEdit,
    )
from maasserver.models.node import Node
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.nodeprobeddetails import get_probed_details


DISPLAYED_NODEGROUP_FIELDS = ('uuid', 'status', 'name', 'cluster_name')


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

        This method is reserved to admin users and returns 403 if the
        user is not an admin.

        Returns 404 if the nodegroup (cluster) is not found.
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

        This method is reserved to admin users and returns 403 if the
        user is not an admin.

        Returns 404 if the nodegroup (cluster) is not found.
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
        """GET a node group.

        Returns 404 if the nodegroup (cluster) is not found.
        """
        return get_object_or_404(NodeGroup, uuid=uuid)

    def accept_all_nodes(self, accept_all):
        """Check for accepting enlisted nodes."""
        if isinstance(accept_all, basestring):
            return accept_all.lower() == 'true'

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

        Returns 404 if the nodegroup (cluster) is not found.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        form = NodeGroupEdit(instance=nodegroup, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    @operation(idempotent=False)
    def import_boot_images(self, request, uuid):
        """Import the pxe files on this cluster controller.

        Returns 404 if the nodegroup (cluster) is not found.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        nodegroup.import_boot_images()
        return HttpResponse(
            "Import of boot images started on cluster %r" % nodegroup.uuid,
            status=httplib.OK)

    @operation(idempotent=True)
    def list_nodes(self, request, uuid):
        """Get the list of node ids that are part of this group.

        Returns 404 if the nodegroup (cluster) is not found.
        """
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

        Returns 404 if the nodegroup (cluster) is not found.
        Returns 403 if the user does not have access to the nodegroup.
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

        Returns 404 if the nodegroup (cluster) is not found.
        Returns 403 if the user does not have access to the nodegroup.
        Returns 400 if the required parameters were not passed.
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
            raise MAASAPIValidationError(form.errors)
        form.save()

        return HttpResponse(status=httplib.OK)

    @admin_method
    @operation(idempotent=False)
    def probe_and_enlist_hardware(self, request, uuid):
        """Add special hardware types.

        :param model: The type of special hardware, 'seamicro15k' and
            'virsh' is supported.
        :type model: unicode

        The following are optional:

        :param accept_all: If true, all enlisted nodes will be
            commissioned.
        :type accept_all: unicode

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
        :param prefix_filter: Only import nodes based on supplied prefix.
        :type prefix_filter: unicode

        Returns 404 if the nodegroup (cluster) is not found.
        Returns 403 if the user does not have access to the nodegroup.
        Returns 400 if the required parameters were not passed.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)

        user = request.user.username
        model = get_mandatory_param(request.data, 'model')
        accept_all = self.accept_all_nodes(
            get_optional_param(request.data, 'accept_all'))
        if model == 'seamicro15k':
            mac = get_mandatory_param(request.data, 'mac')
            username = get_mandatory_param(request.data, 'username')
            password = get_mandatory_param(request.data, 'password')
            power_control = get_optional_param(
                request.data, 'power_control', default='ipmi',
                validator=validators.OneOf(['ipmi', 'restapi', 'restapi2']))

            nodegroup.add_seamicro15k(
                user, mac, username,
                password, power_control=power_control, accept_all=accept_all)
        elif model == 'powerkvm' or model == 'virsh':
            poweraddr = get_mandatory_param(request.data, 'power_address')
            password = get_optional_param(
                request.data, 'power_pass', default=None)
            prefix_filter = get_optional_param(
                request.data, 'prefix_filter', default=None)

            nodegroup.add_virsh(
                user, poweraddr, password=password,
                prefix_filter=prefix_filter, accept_all=accept_all)
        elif model == 'ucsm':
            self.do_probe_and_enlist_ucsm(nodegroup, request, user)
        elif model == 'mcsm':
            self.do_probe_and_enlist_mscm(nodegroup, request, user)
        elif model == 'msftocs':
            self.do_probe_and_enlist_msftocs(nodegroup, request, user)
        elif model == 'esxi':
            poweraddr = get_mandatory_param(request.data, 'address')
            username = get_mandatory_param(request.data, 'username')
            password = get_mandatory_param(request.data, 'password')
            prefix_filter = get_optional_param(
                request.data, 'prefix_filter', default=None)

            nodegroup.add_esxi(
                username, poweraddr, password=password,
                prefix_filter=prefix_filter, accept_all=accept_all)
        else:
            return HttpResponse(status=httplib.BAD_REQUEST)

        return HttpResponse(status=httplib.OK)

    def do_probe_and_enlist_ucsm(self, nodegroup, request, user):
        """Probe and enlist UCSM"""
        url = get_mandatory_param(request.data, 'url')
        username = get_mandatory_param(request.data, 'username')
        password = get_mandatory_param(request.data, 'password')
        accept_all = self.accept_all_nodes(
            get_optional_param(request.data, 'accept_all'))
        nodegroup.enlist_nodes_from_ucsm(
            user, url, username, password, accept_all)

    @admin_method
    @operation(idempotent=False)
    def probe_and_enlist_ucsm(self, request, uuid):
        """Add the nodes from a Cisco UCS Manager.

        **Warning: this API is deprecated in favor of
        probe_and_enlist_hardware.**

        :param url: The URL of the UCS Manager API.
        :type url: unicode
        :param username: The username for the API.
        :type username: unicode
        :param password: The password for the API.
        :type password: unicode
        :param accept_all: If true, all enlisted nodes will be
            commissioned.
        :type accept_all: unicode

        Returns 404 if the nodegroup (cluster) is not found.
        Returns 403 if the user does not have access to the nodegroup.
        Returns 400 if the required parameters were not passed.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        user = request.user.username

        self.do_probe_and_enlist_ucsm(nodegroup, request, user)

        return HttpResponse(status=httplib.OK)

    def do_probe_and_enlist_mscm(self, nodegroup, request, user):
        """Probe and enlist MSCM"""
        host = get_mandatory_param(request.data, 'host')
        username = get_mandatory_param(request.data, 'username')
        password = get_mandatory_param(request.data, 'password')
        accept_all = self.accept_all_nodes(
            get_optional_param(request.data, 'accept_all'))
        nodegroup.enlist_nodes_from_mscm(
            user, host, username, password, accept_all)

    @admin_method
    @operation(idempotent=False)
    def probe_and_enlist_mscm(self, request, uuid):
        """Add the nodes from a Moonshot HP iLO Chassis Manager (MSCM).

        **Warning: this API is deprecated in favor of
        probe_and_enlist_hardware.**

        :param host: IP Address for the MSCM.
        :type host: unicode
        :param username: The username for the MSCM.
        :type username: unicode
        :param password: The password for the MSCM.
        :type password: unicode
        :param accept_all: If true, all enlisted nodes will be
            commissioned.
        :type accept_all: unicode

        Returns 404 if the nodegroup (cluster) is not found.
        Returns 403 if the user does not have access to the nodegroup.
        Returns 400 if the required parameters were not passed.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)

        user = request.user.username
        self.do_probe_and_enlist_mscm(nodegroup, request, user)

        return HttpResponse(status=httplib.OK)

    def do_probe_and_enlist_msftocs(self, nodegroup, request, user):
        """Probe and enlist Microsoft OCS."""
        ip = get_mandatory_param(request.data, 'ip')
        port = get_mandatory_param(request.data, 'port')
        username = get_mandatory_param(request.data, 'username')
        password = get_mandatory_param(request.data, 'password')
        accept_all = self.accept_all_nodes(
            get_optional_param(request.data, 'accept_all'))
        nodegroup.enlist_nodes_from_msftocs(
            user, ip, port, username, password, accept_all)
