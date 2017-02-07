# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "PodHandler",
    "PodsHandler",
    ]

from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
)
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms_pods import (
    ComposeMachineForm,
    PodForm,
)
from maasserver.models.bmc import Pod
from piston3.utils import rc
from provisioningserver.drivers.pod import Capabilities

# Pod fields exposed on the API.
DISPLAYED_POD_FIELDS = (
    'id',
    'name',
    'type',
    'architectures',
    'capabilities',
    'total',
    'used',
    'available',
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
        return result

    @classmethod
    def available(cls, pod):
        result = {}
        used = cls.used(pod)
        for key, value in cls.total(pod).items():
            result[key] = value - used[key]
        return result

    @admin_method
    def update(self, request, id):
        """Update a specific Pod.

        :param name: Name for the pod (optional).

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
        pod.delete()
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
        :param memory: Minimum amount of memory (MiB).
        :param cpu_speed: Minimum amount of CPU speed (MHz).
        :param architecture: Architecture for the machine. Must be an
            architecture that the pod supports.

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

        :param type: Type of pod to create.
        :param name: Name for the pod (optional).

        Returns 503 if the pod could not be discovered.
        Returns 404 if the pod is not found.
        Returns 403 if the user does not have permission to create a pod.
        """
        form = PodForm(data=request.data, request=request)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)
