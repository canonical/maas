# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Pod`."""

__all__ = [
    "PodHandler",
    "PodsHandler",
    ]

from django.shortcuts import get_object_or_404
from formencode.validators import String
from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_mandatory_param
from maasserver.enum import NODE_CREATION_TYPE
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.pods import (
    ComposeMachineForm,
    PodForm,
)
from maasserver.models.bmc import Pod
from maasserver.models.node import Machine
from maasserver.utils.django_urls import reverse
from piston3.utils import rc
from provisioningserver.drivers.pod import Capabilities

# Pod fields exposed on the API.
DISPLAYED_POD_FIELDS = (
    'id',
    'name',
    'tags',
    'type',
    'architectures',
    'capabilities',
    'total',
    'used',
    'available',
    'zone',
    'cpu_over_commit_ratio',
    'memory_over_commit_ratio',
    'storage_pools',
    'default_pool',
    )


class PodHandler(OperationsHandler):
    """Manage an individual pod.

    The pod is identified by its id.
    """
    api_doc_section_name = "Pod"

    create = None
    model = Pod
    fields = DISPLAYED_POD_FIELDS

    @classmethod
    def type(cls, pod):
        return pod.power_type

    @classmethod
    def total(cls, pod):
        result = {
            'cores': pod.cores,
            'memory': pod.memory,
            'local_storage': pod.local_storage,
        }
        if Capabilities.FIXED_LOCAL_STORAGE in pod.capabilities:
            result['local_disks'] = pod.local_disks
        if Capabilities.ISCSI_STORAGE in pod.capabilities:
            result['iscsi_storage'] = pod.iscsi_storage
        return result

    @classmethod
    def used(cls, pod):
        result = {
            'cores': pod.get_used_cores(),
            'memory': pod.get_used_memory(),
            'local_storage': pod.get_used_local_storage(),
        }
        if Capabilities.FIXED_LOCAL_STORAGE in pod.capabilities:
            result['local_disks'] = pod.get_used_local_disks()
        if Capabilities.ISCSI_STORAGE in pod.capabilities:
            result['iscsi_storage'] = pod.get_used_iscsi_storage()
        return result

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
            pools.append({
                'id': pool.pool_id,
                'name': pool.name,
                'type': pool.pool_type,
                'path': pool.path,
                'total': pool.storage,
                'used': used,
                'available': pool.storage - used,
                'default': pool.id == default_id
            })
        return pools

    @admin_method
    def update(self, request, id):
        """Update a specific Pod.

        :param name: Name for the pod
        :type name: unicode
        :param default_pool: Default resource pool that composed machines
            get assigned to by default.
        :type default_pool: unicode
        :param cpu_over_commit_ratio: CPU over commit ratio
        :type cpu_over_commit_ratio: unicode
        :param memory_over_commit_ratio: Memory over commit ratio
        :type memory_over_commit_ratio: unicode
        :param default_storage_pool: Default storage pool (used when pod has
            storage pools).
        :type default_storage_pool: unicode
        :param power_address: Address for power control of the pod
        :type power_address: unicode
        :param power_pass: Password for power control of the pod
        :type power_pass: unicode
        :param zone: Name of the zone for the pod
        :type zone: unicode
        :param tags: A tag or tags (separated by comma) for the pod.
        :type tags: unicode

        Note: 'type' cannot be updated on a Pod. The Pod must be deleted and
        re-added to change the type.

        Returns 404 if the pod is not found.
        Returns 403 if the user does not have permission to update the pod.
        """
        pod = get_object_or_404(Pod, id=id)
        form = PodForm(data=request.data, instance=pod, request=request)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    def delete(self, request, id):
        """Delete a specific Pod.

        Returns 404 if the pod is not found.
        Returns 403 if the user does not have permission to delete the pod.
        Returns 204 if the pod is successfully deleted.
        """
        pod = get_object_or_404(Pod, id=id)
        # Calculate the wait time based on the number of none pre-existing
        # machines. We allow maximum of 60 seconds per machine plus 60 seconds
        # for the pod.
        num_machines = Machine.objects.filter(bmc=pod)
        num_machines = num_machines.exclude(
            creation_type=NODE_CREATION_TYPE.PRE_EXISTING)
        pod.async_delete().wait((num_machines.count() * 60) + 60)
        return rc.DELETED

    @admin_method
    @operation(idempotent=False)
    def refresh(self, request, id):
        """Refresh a specific Pod.

        Performs pod discovery and updates all discovered information and
        discovered machines.

        Returns 404 if the pod is not found.
        Returns 403 if the user does not have permission to refresh the pod.
        """
        pod = get_object_or_404(Pod, id=id)
        form = PodForm(data=request.data, instance=pod, request=request)
        pod = form.discover_and_sync_pod()
        return pod

    @admin_method
    @operation(idempotent=True)
    def parameters(self, request, id):
        """Obtain pod parameters.

        This method is reserved for admin users and returns a 403 if the
        user is not one.

        This returns the pod parameters, if any, configured for a
        pod. For some types of pod this will include private
        information such as passwords and secret keys.

        Returns 404 if the pod is not found.
        """
        pod = get_object_or_404(Pod, id=id)
        return pod.power_parameters

    @admin_method
    @operation(idempotent=False)
    def compose(self, request, id):
        """Compose a machine from Pod.

        All fields below are optional:

        :param cores: Minimum number of CPU cores.
        :type cores: unicode
        :param memory: Minimum amount of memory (MiB).
        :type memory: unicode
        :param cpu_speed: Minimum amount of CPU speed (MHz).
        :type cpu_speed: unicode
        :param architecture: Architecture for the machine. Must be an
            architecture that the pod supports.
        :param architecture: unicode
        :param storage: A list of storage constraint identifiers, in the form:
            <label>:<size>(<tag>[,<tag>[,...])][,<label>:...]
        :type storage: unicode
        :param hostname: Hostname for the newly composed machine.
        :type hostname: unicode
        :param domain: ID of domain to place the newly composed machine in.
        :type domain: unicode
        :param zone: ID of zone place the newly composed machine in.
        :type zone: unicode
        :param pool: ID of resource pool to place the newly composed machine
            in.
        :type pool: unicode

        Returns 404 if the pod is not found.
        Returns 403 if the user does not have permission to compose machine.
        """
        pod = get_object_or_404(Pod, id=id)
        if Capabilities.COMPOSABLE not in pod.capabilities:
            raise MAASAPIValidationError("Pod does not support composability.")
        form = ComposeMachineForm(data=request.data, pod=pod, request=request)
        if form.is_valid():
            machine = form.compose()
            return {
                'system_id': machine.system_id,
                'resource_uri': reverse(
                    'machine_handler', kwargs={'system_id': machine.system_id})
            }
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    @operation(idempotent=False)
    def add_tag(self, request, id):
        """Add a tag to Pod.

        :param tag: The tag being added.
        :type tag: unicode

        Returns 404 if the Pod is not found.
        Returns 403 if the user is not allowed to update the Pod.
        """
        tag = get_mandatory_param(request.data, 'tag', String)

        if ',' in tag:
            raise MAASAPIValidationError('Tag may not contain a ",".')

        pod = get_object_or_404(Pod, id=id)
        pod.add_tag(tag)
        pod.save()
        return pod

    @admin_method
    @operation(idempotent=False)
    def remove_tag(self, request, id):
        """Remove a tag from Pod.

        :param tag: The tag being removed.
        :type tag: unicode

        Returns 404 if the Pod is not found.
        Returns 403 if the user is not allowed to update the Pod.
        """
        tag = get_mandatory_param(request.data, 'tag', String)

        pod = get_object_or_404(Pod, id=id)
        pod.remove_tag(tag)
        pod.save()
        return pod

    @classmethod
    def resource_uri(cls, pod=None):
        # This method is called by piston in two different contexts:
        # - when generating an uri template to be used in the documentation
        # (in this case, it is called with node=None).
        # - when populating the 'resource_uri' field of an object
        # returned by the API (in this case, node is a node object).
        pod_id = "id"
        if pod is not None:
            pod_id = pod.id
        return ('pod_handler', (pod_id,))


class PodsHandler(OperationsHandler):
    """Manage the collection of all the pod in the MAAS."""
    api_doc_section_name = "Pods"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('pods_handler', [])

    def read(self, request):
        """List pods.

        Get a listing of all the pods.
        """
        return Pod.objects.all().order_by('id')

    @admin_method
    def create(self, request):
        """Create a Pod.

        :param type: Type of pod to create (rsd, virsh) (required).
        :type name: unicode
        :param power_address: Address for power control of the pod (required).
        :type power_address: unicode
        :param power_user: User for power control of the pod
            (required for rsd).
        :type power_user: unicode
        :param power_pass: Password for power control of the pod
            (required for rsd).
        :type power_pass: unicode
        :param name: Name for the pod (optional).
        :type name: unicode
        :param zone: Name of the zone for the pod (optional).
        :type zone: unicode
        :param default_pool: Default resource pool that composed machines
            get assigned to by default (optional).
        :type default_pool: unicode
        :param tags: A tag or tags (separated by comma) for the pod (optional).
        :type tags: unicode

        Returns 503 if the pod could not be discovered.
        Returns 404 if the pod is not found.
        Returns 403 if the user does not have permission to create a pod.
        """
        form = PodForm(data=request.data, request=request)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)
