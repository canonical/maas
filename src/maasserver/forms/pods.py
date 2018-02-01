# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Pod forms."""

__all__ = [
    "PodForm",
    ]

from functools import partial

import crochet
from django import forms
from django.core.exceptions import ValidationError
from django.forms import (
    BooleanField,
    CharField,
    ChoiceField,
    IntegerField,
    ModelChoiceField,
)
from maasserver.clusterrpc import driver_parameters
from maasserver.clusterrpc.driver_parameters import (
    get_driver_parameters_from_json,
)
from maasserver.clusterrpc.pods import (
    compose_machine,
    discover_pod,
    get_best_discovered_result,
)
from maasserver.enum import (
    BMC_TYPE,
    NODE_CREATION_TYPE,
)
from maasserver.exceptions import PodProblem
from maasserver.forms import MAASModelForm
from maasserver.models import (
    BMC,
    BMCRoutableRackControllerRelationship,
    Domain,
    Machine,
    Node,
    Pod,
    RackController,
    ResourcePool,
    Zone,
)
from maasserver.node_constraint_filter_forms import (
    get_storage_constraints_from_string,
    storage_validator,
)
from maasserver.rpc import getClientFromIdentifiers
from maasserver.utils.forms import set_form_error
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
import petname
from provisioningserver.drivers import SETTING_SCOPE
from provisioningserver.drivers.pod import (
    Capabilities,
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
)
from provisioningserver.utils.twisted import asynchronous
from twisted.python.threadable import isInIOThread


def make_unique_hostname():
    """Returns a unique machine hostname."""
    while True:
        hostname = petname.Generate(2, "-")
        if Machine.objects.filter(hostname=hostname).exists():
            continue
        else:
            return hostname


class PodForm(MAASModelForm):

    class Meta:
        model = Pod
        fields = ['name']

    name = forms.CharField(
        label="Name", required=False, help_text=(
            "The name of the pod"))

    def __init__(self, data=None, instance=None, request=None, **kwargs):
        self.is_new = instance is None
        self.request = request
        super(PodForm, self).__init__(
            data=data, instance=instance, **kwargs)
        if data is None:
            data = {}
        type_value = data.get('type', self.initial.get('type'))
        self.drivers_orig = driver_parameters.get_all_power_types_from_racks()
        self.drivers = {
            driver['name']: driver
            for driver in self.drivers_orig
            if driver['driver_type'] == 'pod'
        }
        if len(self.drivers) == 0:
            type_value = ''
        elif type_value not in self.drivers:
            type_value = (
                '' if self.instance is None else self.instance.power_type)
        choices = [
            (name, driver['description'])
            for name, driver in self.drivers.items()
        ]
        self.fields['type'] = forms.ChoiceField(
            required=True, choices=choices, initial=type_value)
        if not self.is_new:
            if self.instance.power_type != '':
                self.initial['type'] = self.instance.power_type

    def _clean_fields(self):
        """Override to dynamically add fields based on the value of `type`
        field."""
        # Process the built-in fields first.
        super(PodForm, self)._clean_fields()
        # If no errors then we re-process with the fields required by the
        # selected type for the pod.
        if len(self.errors) == 0:
            driver_fields = get_driver_parameters_from_json(
                self.drivers_orig, None, scope=SETTING_SCOPE.BMC)
            self.param_fields = (
                driver_fields[self.cleaned_data['type']].field_dict)
            self.fields.update(self.param_fields)
            super(PodForm, self)._clean_fields()

    def clean(self):
        cleaned_data = super(PodForm, self).clean()
        if len(self.drivers) == 0:
            set_form_error(
                self, 'type',
                "No rack controllers are connected, unable to validate.")
        elif (not self.is_new and
                self.instance.power_type != self.cleaned_data.get('type')):
            set_form_error(
                self, 'type',
                "Cannot change the type of a pod. Delete and re-create the "
                "pod with a different type.")
        return cleaned_data

    def save(self, *args, **kwargs):
        """Persist the pod into the database."""
        def check_for_duplicate(power_type, power_parameters):
            # When the Pod is new try to get a BMC of the same type and
            # parameters to convert the BMC to a new Pod. When the Pod is not
            # new the form will use the already existing pod instance to update
            # those fields. If updating the fields causes a duplicate BMC then
            # a validation erorr will be raised from the model level.
            if self.is_new:
                bmc = BMC.objects.filter(
                    power_type=power_type,
                    power_parameters=power_parameters).first()
                if bmc is not None:
                    if bmc.bmc_type == BMC_TYPE.BMC:
                        # Convert the BMC to a Pod and set as the instance for
                        # the PodForm.
                        bmc.bmc_type = BMC_TYPE.POD
                        bmc.default_pool = (
                            ResourcePool.objects.get_default_resource_pool())
                        return bmc.as_pod()
                    else:
                        # Pod already exists with the same power_type and
                        # parameters.
                        raise ValidationError(
                            "Pod %s with type and "
                            "parameters already exist." % bmc.name)

        def update_obj(existing_obj):
            if existing_obj is not None:
                self.instance = existing_obj
            self.instance = super(PodForm, self).save(commit=False)
            self.instance.power_type = power_type
            self.instance.power_parameters = power_parameters
            return self.instance

        power_type = self.cleaned_data['type']
        # Set power_parameters to the generated param_fields.
        power_parameters = {
            param_name: self.cleaned_data[param_name]
            for param_name in self.param_fields.keys()
            if param_name in self.cleaned_data
        }

        if isInIOThread():
            # Running in twisted reactor, do the work inside the reactor.
            d = deferToDatabase(
                transactional(check_for_duplicate),
                power_type, power_parameters)
            d.addCallback(update_obj)
            d.addCallback(lambda _: self.discover_and_sync_pod())
            return d
        else:
            # Perform the actions inside the executing thread.
            existing_obj = check_for_duplicate(power_type, power_parameters)
            if existing_obj is not None:
                self.instance = existing_obj
            self.instance = update_obj(self.instance)
            return self.discover_and_sync_pod()

    def discover_and_sync_pod(self):
        """Discover and sync the pod information."""
        def update_db(result):
            discovered_pod, discovered = result

            # When called with an instance that has no name, be sure to set
            # it before going any further. If this is a new instance this will
            # also create it in the database.
            if not self.instance.name:
                self.instance.set_random_name()
            self.instance.sync(discovered_pod, self.request.user)

            # Save which rack controllers can route and which cannot.
            discovered_rack_ids = [
                rack_id for rack_id, _ in discovered[0].items()]
            for rack_controller in RackController.objects.all():
                routable = rack_controller.system_id in discovered_rack_ids
                bmc_route_model = BMCRoutableRackControllerRelationship
                relation, created = (
                    bmc_route_model.objects.get_or_create(
                        bmc=self.instance.as_bmc(),
                        rack_controller=rack_controller,
                        defaults={'routable': routable}))
                if not created and relation.routable != routable:
                    relation.routable = routable
                    relation.save()
            return self.instance

        if isInIOThread():
            # Running in twisted reactor, do the work inside the reactor.
            d = discover_pod(
                self.instance.power_type, self.instance.power_parameters,
                pod_id=self.instance.id, name=self.instance.name)
            d.addCallback(
                lambda discovered: (
                    get_best_discovered_result(discovered), discovered))

            def catch_no_racks(result):
                discovered_pod, discovered = result
                if discovered_pod is None:
                    raise PodProblem(
                        "Unable to start the pod discovery process. "
                        "No rack controllers connected.")
                return discovered_pod, discovered

            def wrap_errors(failure):
                if failure.check(PodProblem):
                    return failure
                else:
                    raise PodProblem(str(failure.value))

            d.addCallback(catch_no_racks)
            d.addCallback(partial(deferToDatabase, transactional(update_db)))
            d.addErrback(wrap_errors)
            return d
        else:
            # Perform the actions inside the executing thread.
            try:
                discovered = discover_pod(
                    self.instance.power_type, self.instance.power_parameters,
                    pod_id=self.instance.id, name=self.instance.name)
            except Exception as exc:
                raise PodProblem(str(exc)) from exc

            # Use the first discovered pod object. All other objects are
            # ignored. The other rack controllers that also provided a result
            # can route to the pod.
            try:
                discovered_pod = get_best_discovered_result(discovered)
            except Exception as error:
                raise PodProblem(str(error))
            if discovered_pod is None:
                raise PodProblem(
                    "Unable to start the pod discovery process. "
                    "No rack controllers connected.")
            return update_db((discovered_pod, discovered))


class ComposeMachineForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        if self.request is None:
            raise ValueError("'request' kwargs is required.")
        self.pod = kwargs.pop('pod', None)
        if self.pod is None:
            raise ValueError("'pod' kwargs is required.")
        super(ComposeMachineForm, self).__init__(*args, **kwargs)

        # Build the fields based on the pod and current pod hints.
        self.fields['cores'] = IntegerField(
            min_value=1, max_value=self.pod.hints.cores, required=False)
        self.initial['cores'] = 1
        self.fields['memory'] = IntegerField(
            min_value=1024, max_value=self.pod.hints.memory, required=False)
        self.initial['memory'] = 1024
        self.fields['architecture'] = ChoiceField(
            choices=[
                (arch, arch)
                for arch in self.pod.architectures
            ], required=False)
        self.initial['architecture'] = self.pod.architectures[0]
        if self.pod.hints.cpu_speed > 0:
            self.fields['cpu_speed'] = IntegerField(
                min_value=300, max_value=self.pod.hints.cpu_speed,
                required=False)
        else:
            self.fields['cpu_speed'] = IntegerField(
                min_value=300, required=False)

        def duplicated_hostname(hostname):
            if Node.objects.filter(hostname=hostname).exists():
                raise ValidationError(
                    'Node with hostname "%s" already exists' % hostname)

        self.fields['hostname'] = CharField(
            required=False, validators=[duplicated_hostname])
        self.initial['hostname'] = make_unique_hostname()
        self.fields['domain'] = ModelChoiceField(
            required=False, queryset=Domain.objects.all())
        self.initial['domain'] = Domain.objects.get_default_domain()
        self.fields['zone'] = ModelChoiceField(
            required=False, queryset=Zone.objects.all())
        self.initial['zone'] = Zone.objects.get_default_zone()
        self.fields['storage'] = CharField(
            validators=[storage_validator], required=False)
        self.initial['storage'] = 'root:8(local)'
        self.fields['skip_commissioning'] = BooleanField(required=False)
        self.initial['skip_commissioning'] = False

    def get_value_for(self, field):
        """Get the value for `field`. Use initial data if missing or set to
        `None` in the cleaned_data."""
        value = self.cleaned_data.get(field)
        if value:
            return value
        elif field in self.initial:
            return self.initial[field]
        else:
            return None

    def get_requested_machine(self):
        """Return the `RequestedMachine`."""
        # XXX blake_r 2017-04-04: Interfaces are hard coded at the
        # moment. Will be extended later.
        block_devices = []
        constraints = get_storage_constraints_from_string(
            self.get_value_for('storage'))
        for _, size, tags in constraints:
            if tags is None:
                tags = []
            block_devices.append(
                RequestedMachineBlockDevice(size=size, tags=tags))
        return RequestedMachine(
            hostname=self.get_value_for('hostname'),
            architecture=self.get_value_for('architecture'),
            cores=self.get_value_for('cores'),
            memory=self.get_value_for('memory'),
            cpu_speed=self.get_value_for('cpu_speed'),
            block_devices=block_devices,
            interfaces=[RequestedMachineInterface()])

    def save(self):
        """Prevent from usage."""
        raise AttributeError("Use `compose` instead of `save`.")

    def compose(
            self, timeout=120, creation_type=NODE_CREATION_TYPE.MANUAL,
            skip_commissioning=None):
        """Compose the machine.

        Internal operation of this form is asynchronously. It will block the
        calling thread until the asynchronous operation is complete. Adjust
        `timeout` to minimize the maximum wait for the asynchronous operation.
        """
        if skip_commissioning is None:
            skip_commissioning = self.get_value_for('skip_commissioning')

        def create_and_sync(result):
            discovered_machine, pod_hints = result
            created_machine = self.pod.create_machine(
                discovered_machine, self.request.user,
                skip_commissioning=skip_commissioning,
                creation_type=creation_type,
                domain=self.get_value_for('domain'),
                zone=self.get_value_for('zone'))
            self.pod.sync_hints(pod_hints)
            return created_machine

        if isInIOThread():
            # Running under the twisted reactor, before the work from inside.
            d = deferToDatabase(transactional(self.pod.get_client_identifiers))
            d.addCallback(getClientFromIdentifiers)
            d.addCallback(
                compose_machine, self.pod.power_type,
                self.pod.power_parameters, self.get_requested_machine(),
                pod_id=self.pod.id, name=self.pod.name)
            d.addCallback(
                partial(deferToDatabase, transactional(create_and_sync)))
            return d
        else:
            # Running outside of reactor. Do the work inside and then finish
            # the work outside.
            @asynchronous
            def wrap_compose_machine(
                    client_idents, pod_type, parameters, request,
                    pod_id, name):
                """Wrapper to get the client."""
                d = getClientFromIdentifiers(client_idents)
                d.addCallback(
                    compose_machine, pod_type, parameters, request,
                    pod_id=pod_id, name=name)
                return d

            try:
                result = wrap_compose_machine(
                    self.pod.get_client_identifiers(),
                    self.pod.power_type,
                    self.pod.power_parameters,
                    self.get_requested_machine(),
                    pod_id=self.pod.id,
                    name=self.pod.name).wait(timeout)
            except crochet.TimeoutError:
                raise PodProblem(
                    "Unable to compose a machine because '%s' driver "
                    "timed out after %d seconds." % (
                        self.pod.power_type, timeout))
            return create_and_sync(result)


class ComposeMachineForPodsForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        if self.request is None:
            raise ValueError("'request' kwargs is required.")
        self.pods = kwargs.pop('pods', None)
        if self.pods is None:
            raise ValueError("'pods' kwargs is required.")
        super(ComposeMachineForPodsForm, self).__init__(*args, **kwargs)
        self.pod_forms = [
            ComposeMachineForm(request=self.request, data=self.data, pod=pod)
            for pod in self.pods
        ]

    def save(self):
        """Prevent from usage."""
        raise AttributeError("Use `compose` instead of `save`.")

    def compose(self):
        """Composed machine from available pod."""
        non_commit_forms = [
            form
            for form in self.valid_pod_forms
            if Capabilities.OVER_COMMIT not in form.pod.capabilities
        ]
        commit_forms = [
            form
            for form in self.valid_pod_forms
            if Capabilities.OVER_COMMIT in form.pod.capabilities
        ]
        # First, try to compose a machine from non-commitable pods.
        for form in non_commit_forms:
            try:
                return form.compose(
                    skip_commissioning=True,
                    creation_type=NODE_CREATION_TYPE.DYNAMIC)
            except:
                continue
        # Second, try to compose a machine from commitable pods
        for form in commit_forms:
            try:
                return form.compose(
                    skip_commissioning=True,
                    creation_type=NODE_CREATION_TYPE.DYNAMIC)
            except:
                continue
        # No machine found.
        return None

    def clean(self):
        self.valid_pod_forms = [
            pod_form
            for pod_form in self.pod_forms
            if pod_form.is_valid()
        ]
        if len(self.valid_pod_forms) == 0:
            self.add_error(
                "__all__", "No current pod resources match constraints.")
