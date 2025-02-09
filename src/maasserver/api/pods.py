# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Pod`."""

from django.core.exceptions import PermissionDenied
from django.urls import reverse
from formencode.validators import String
from piston3.utils import rc

from maasserver.api.support import (
    admin_method,
    deprecated,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_mandatory_param
from maasserver.exceptions import MAASAPIValidationError, PodProblem
from maasserver.forms.pods import ComposeMachineForm, DeletePodForm, PodForm
from maasserver.models.bmc import Pod
from maasserver.models.virtualmachine import get_vm_host_used_resources
from maasserver.permissions import PodPermission
from maasserver.vmhost import discover_and_sync_vmhost
from provisioningserver.drivers.pod import Capabilities

# Pod fields exposed on the API.
DISPLAYED_POD_FIELDS = (
    "id",
    "name",
    "tags",
    "type",
    "architectures",
    "capabilities",
    "total",
    "used",
    "available",
    "zone",
    "cpu_over_commit_ratio",
    "memory_over_commit_ratio",
    "storage_pools",
    "pool",
    "host",
    "default_macvlan_mode",
    "version",
)


class VmHostHandler(OperationsHandler):
    """
    Manage an individual VM host.

    A VM host is identified by its id.
    """

    api_doc_section_name = "Virtual machine host"

    create = None
    model = Pod
    fields = DISPLAYED_POD_FIELDS

    @classmethod
    def type(cls, pod):
        return pod.power_type

    @classmethod
    def total(cls, pod):
        return {
            "cores": pod.cores,
            "memory": pod.memory,
            "local_storage": pod.local_storage,
        }

    @classmethod
    def used(cls, pod):
        used_resources = get_vm_host_used_resources(pod)
        return {
            "cores": used_resources.cores,
            "memory": used_resources.total_memory,
            "local_storage": used_resources.storage,
        }

    @classmethod
    def available(cls, pod):
        result = {}
        used = cls.used(pod)
        for key, value in cls.total(pod).items():
            result[key] = value - used[key]
        return result

    @classmethod
    def storage_pools(cls, pod):
        pools = []
        default_id = pod.default_storage_pool_id
        for pool in pod.storage_pools.all():
            used = pool.get_used_storage()
            pools.append(
                {
                    "id": pool.pool_id,
                    "name": pool.name,
                    "type": pool.pool_type,
                    "path": pool.path,
                    "total": pool.storage,
                    "used": used,
                    "available": pool.storage - used,
                    "default": pool.id == default_id,
                }
            )
        return pools

    @classmethod
    def host(cls, pod):
        system_id = None
        if pod.host is not None:
            system_id = pod.host.system_id
        # __incomplete__ let's user know that this
        # object has more data associated with it.
        return {"system_id": system_id, "__incomplete__": True}

    @admin_method
    def update(self, request, id):
        """@description-title Update a specific VM host
        @description Update a specific VM host by ID.

        Note: A VM host's 'type' cannot be updated. The VM host must be deleted
        and re-added to change the type.

        @param (url-string) "{id}" [required=true] The VM host's ID.
        @param (string) "name" [required=false] The VM host's name.
        @param (string) "pool" [required=false] The name of the resource pool
        associated with this VM host -- composed machines will be assigned to this
        resource pool by default.
        @param (int) "cpu_over_commit_ratio" [required=false] CPU overcommit
        ratio (0-10)
        @param (int) "memory_over_commit_ratio" [required=false] CPU overcommit
        ratio (0-10)
        @param (string) "default_storage_pool" [required=false] Default KVM
        storage pool to use when the VM host has storage pools.
        @param (string) "power_address" [required=false] Address for power
        control of the VM host.
        @param-example "power_address"
        ``Virsh: qemu+ssh://172.16.99.2/system``
        @param (string) "power_pass" [required=false] Password for access to
        power control of the VM host.
        @param (string) "zone" [required=false] The VM host's zone.
        @param (string) "default_macvlan_mode" [required=false] Default macvlan
        mode for VM hosts that use it: bridge, passthru, private, vepa.
        @param (string) "tags" [required=false] Tag or tags (command separated)
        associated with the VM host.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON VM host object.
        @success-example "success-json" [exkey=update-vmhost] placeholder text

        @error (http-status-code) "404" 404 -- The VM host's ID was not found.
        @error (http-status-code) "403" 403 -- The current user does not have
        permission to update the VM host.

        """
        pod = Pod.objects.get_pod_or_404(id, request.user, PodPermission.edit)
        form = PodForm(data=request.data, instance=pod, request=request)
        if form.is_valid():
            pod = form.save()
        else:
            raise MAASAPIValidationError(form.errors)

        _try_sync_and_save(pod, request.user)
        return pod

    @admin_method
    def delete(self, request, id):
        """@description-title Deletes a VM host
        @description Deletes a VM host with the given ID.

        @param (int) "{id}" [required=true] The VM host's ID.
        @param (boolean) "decompose" [required=false] Whether to also also
        decompose all machines in the VM host on removal. If not provided, machines
        will not be removed.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" No VM host with that ID can be found.
        @error-example "not-found"
            No Pod matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        to delete the VM host.
        @error-example (content) "no-perms"
            This method is reserved for admin users.

        """
        pod = Pod.objects.get_pod_or_404(id, request.user, PodPermission.edit)
        form = DeletePodForm(data=request.GET)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        pod.delete_and_wait(decompose=form.cleaned_data["decompose"])
        return rc.DELETED

    @admin_method
    @operation(idempotent=False)
    def refresh(self, request, id):
        """@description-title Refresh a VM host
        @description Performs VM host discovery and updates all discovered
        information and discovered machines.

        @param (int) "{id}" [required=true] The VM host's ID.

        @success (json) "success-json" A VM host JSON object.
        @success-example "success-json" [exkey=refresh-vmhost] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" No VM host with that ID can be found.
        @error-example "not-found"
            No Pod matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        to delete the VM host.
        @error-example (content) "no-perms"
            This method is reserved for admin users.
        """
        pod = Pod.objects.get_pod_or_404(id, request.user, PodPermission.edit)
        return discover_and_sync_vmhost(pod, request.user)

    @admin_method
    @operation(idempotent=True)
    def parameters(self, request, id):
        """@description-title Obtain VM host parameters
        @description This returns a VM host's configuration parameters. For some
        types of VM host, this will include private information such as passwords
        and secret keys.

        Note: This method is reserved for admin users.

        @param (int) "{id}" [required=true] The VM host's ID.

        @success (http-status-code) "200" 200
        @success (json) "success_json" A JSON object containing the VM host's
        configuration parameters.
        @success-example "success_json" [exkey=parameters] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" No VM host with that ID can be found.
        @error-example "not-found"
            No Pod matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        to delete the VM host.
        @error-example (content) "no-perms"
            This method is reserved for admin users.
        """
        pod = Pod.objects.get_pod_or_404(id, request.user, PodPermission.edit)
        return pod.get_power_parameters()

    @admin_method
    @operation(idempotent=False)
    def compose(self, request, id):
        """@description-title Compose a virtual machine on the host.
        @description Compose a new machine from a VM host.

        @param (int) "cores" [required=false] The minimum number of CPU cores.
        @param (int) "memory" [required=false] The minimum amount of memory,
        specified in MiB (e.g. 2 MiB == 2*1024*1024).
        @param (boolean) "hugepages_backed" [required=false] Whether to request
        hugepages backing for the machine.
        @param (int) "pinned_cores" [required=false] List of host CPU cores
        to pin the VM to. If this is passed, the "cores" parameter is ignored.
        @param (int) "cpu_speed" [required=false] The minimum CPU speed,
        specified in MHz.
        @param (string) "architecture" [required=false] The architecture of
        the new machine (e.g. amd64). This must be an architecture the VM host
        supports.
        @param (string) "storage" [required=false] A list of storage
        constraint identifiers in the form ``label:size(tag,tag,...),
        label:size(tag,tag,...)``. For more information please see the CLI
        VM host management page of the official MAAS documentation.
        @param (string) "interfaces" [required=false,formatting=true] A
        labeled constraint map associating constraint labels with desired
        interface properties. MAAS will assign interfaces that match the
        given interface properties.

        Format: ``label:key=value,key=value,...``

        Keys:

        - ``id``: Matches an interface with the specific id
        - ``fabric``: Matches an interface attached to the specified fabric.
        - ``fabric_class``: Matches an interface attached to a fabric
          with the specified class.
        - ``ip``: Matches an interface whose VLAN is on the subnet implied by
          the given IP address, and allocates the specified IP address for
          the machine on that interface (if it is available).
        - ``mode``: Matches an interface with the specified mode. (Currently,
          the only supported mode is "unconfigured".)
        - ``name``: Matches an interface with the specified name.
          (For example, "eth0".)
        - ``hostname``: Matches an interface attached to the node with
          the specified hostname.
        - ``subnet``: Matches an interface attached to the specified subnet.
        - ``space``: Matches an interface attached to the specified space.
        - ``subnet_cidr``: Matches an interface attached to the specified
          subnet CIDR. (For example, "192.168.0.0/24".)
        - ``type``: Matches an interface of the specified type. (Valid
          types: "physical", "vlan", "bond", "bridge", or "unknown".)
        - ``vlan``: Matches an interface on the specified VLAN.
        - ``vid``: Matches an interface on a VLAN with the specified VID.
        - ``tag``: Matches an interface tagged with the specified tag.
        @param (string) "hostname" [required=false] The hostname of the newly
        composed machine.
        @param (int) "domain" [required=false] The ID of the domain in which
        to put the newly composed machine.
        @param (int) "zone" [required=false] The ID of the zone in which to
        put the newly composed machine.
        @param (int) "pool" [required=false] The ID of the pool in which to
        put the newly composed machine.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the new
        machine ID and resource URI.
        @success-example (json) "success-json" [exkey=compose] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" No VM host with that ID can be found.
        @error-example "not-found"
            No Pod matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        to delete the VM host.
        @error-example (content) "no-perms"
            This method is reserved for admin users.
        """
        pod = Pod.objects.get_pod_or_404(
            id, request.user, PodPermission.compose
        )
        if Capabilities.COMPOSABLE not in pod.capabilities:
            raise MAASAPIValidationError(
                "VM host does not support composability."
            )
        form = ComposeMachineForm(data=request.data, pod=pod, request=request)
        if form.is_valid():
            machine = form.compose()
            return {
                "system_id": machine.system_id,
                "resource_uri": reverse(
                    "machine_handler", kwargs={"system_id": machine.system_id}
                ),
            }
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    @operation(idempotent=False)
    def add_tag(self, request, id):
        """@description-title Add a tag to a VM host
        @description Adds a tag to a given VM host.

        @param (int) "{id}" [required=true] The VM host's ID.
        @param (string) "tag" [required=true] The tag to add.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object
        @success-example (json) "success-json" [exkey=add-tag] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" No VM host with that ID can be found.
        @error-example "not-found"
            No Pod matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        to delete the VM host.
        @error-example (content) "no-perms"
            This method is reserved for admin users.
        """
        tag = get_mandatory_param(request.data, "tag", String)

        if "," in tag:
            raise MAASAPIValidationError('Tag may not contain a ",".')

        pod = Pod.objects.get_pod_or_404(id, request.user, PodPermission.edit)
        pod.add_tag(tag)
        pod.save()
        return pod

    @admin_method
    @operation(idempotent=False)
    def remove_tag(self, request, id):
        """@description-title Remove a tag from a VM host
        @description Removes a given tag from a VM host.

        @param (int) "{id}" [required=true] The VM host's ID.
        @param (string) "tag" [required=true] The tag to add.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object.
        @success-example (json) "success-json" [exkey=remove-tag] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" No VM host with that ID can be found.
        @error-example "not-found"
            No Pod matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        to delete the VM host.
        @error-example (content) "no-perms"
            This method is reserved for admin users.
        """
        tag = get_mandatory_param(request.data, "tag", String)

        pod = Pod.objects.get_pod_or_404(id, request.user, PodPermission.edit)
        pod.remove_tag(tag)
        pod.save()
        return pod

    @classmethod
    def resource_uri(cls, pod=None):
        pod_id = pod.id if pod else "id"
        return ("vm_host_handler", (pod_id,))


# Pods are being renamed to VM hosts. Keep the old name on the API as well for
# backwards-compatibility.
@deprecated(use=VmHostHandler)
class PodHandler(VmHostHandler):
    """
    Manage an individual Pod.
    """

    api_doc_section_name = "Pod"

    @classmethod
    def resource_uri(cls, pod=None):
        pod_id = pod.id if pod else "id"
        return ("pod_handler", (pod_id,))


class VmHostsHandler(OperationsHandler):
    """
    Manage the collection of all the VM hosts in MAAS.
    """

    api_doc_section_name = "Virtual machine hosts"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("vm_hosts_handler", [])

    def read(self, request):
        """@description-title List VM hosts
        @description Get a listing of all VM hosts.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        VM host objects.
        @success-example (json) "success-json" [exkey=read-vmhosts]
        placeholder text
        """
        return Pod.objects.get_pods(request.user, PodPermission.view).order_by(
            "id"
        )

    @admin_method
    def create(self, request):
        """@description-title Create a VM host
        @description Create or discover a new VM host.

        @param (string) "type" [required=true] The type of VM host to create:
        ``lxd`` or ``virsh``.
        @param (string) "power_address" [required=true] Address that gives
        MAAS access to the VM host power control. For example, for virsh
        ``qemu+ssh://172.16.99.2/system``
        For ``lxd``, this is just the address of the host.
        @param (string) "power_user" [required=true] Username to use for
        power control of the VM host. Required for ``virsh``
        VM hosts that do not have SSH set up for public-key authentication.
        @param (string) "power_pass" [required=true] Password to use for
        power control of the VM host. Required ``virsh`` VM hosts that do
        not have SSH set up for public-key authentication and for ``lxd``
        if the MAAS certificate is not registered already in the LXD server.
        @param (string) "name" [required=false] The new VM host's name.
        @param (string) "zone" [required=false] The new VM host's zone.
        @param (string) "pool" [required=false] The name of the resource
        pool the new VM host will belong to. Machines composed from this VM host
        will be assigned to this resource pool by default.
        @param (string) "tags" [required=false] A tag or list of tags (
        comma delimited) to assign to the new VM host.
        @param (string) "project" [required=false] For ``lxd`` VM hosts, the
        project that MAAS will manage. If not provided, the ``default`` project
        will be used. If a nonexistent name is given, a new project with that
        name will be created.
        @param (string) "certificate" [required=false]: X.509 certificate used
        to verify the identity of the user. If ``certificate`` and ``key`` are
        not provided, and the VM created is LXD type, a X.509 certificate will
        be created.
        @param (string) "key" [required=false]: private key used for
        authentication. If ``certificate`` and ``key`` are not provided, and
        the VM created is LXD type, a RSA key will be created.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a VM host object.
        @success-example (json) "success-json" [exkey=create] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" No VM host with that ID can be found.
        @error-example "not-found"
            No Pod matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        to delete the VM host.
        @error-example (content) "no-perms"
            This method is reserved for admin users.

        @error (http-status-code) "503" 503
        @error (content) "failed-login" MAAS could not find or could not
            authenticate with the VM host.
        @error-example (content) "failed-login"
            Failed talking to VM host: Failed to authenticate to the VM host.

        """
        if not request.user.has_perm(PodPermission.create):
            raise PermissionDenied()
        form = PodForm(data=request.data, request=request)
        if form.is_valid():
            pod = form.save()
        else:
            raise MAASAPIValidationError(form.errors)

        _try_sync_and_save(pod, request.user)
        return pod


# Pods are being renamed to VM hosts. Keep the old name on the API as well for
# backwards-compatibility.
@deprecated(use=VmHostsHandler)
class PodsHandler(VmHostsHandler):
    """
    Manage the collection of all the pods in the MAAS.
    """

    api_doc_section_name = "Pods"

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("pods_handler", [])


def _try_sync_and_save(pod, user):
    try:
        discover_and_sync_vmhost(pod, user)
    except PodProblem:
        # if discovery fails, still save the object as is, to allow
        # config changes
        pod.save()
