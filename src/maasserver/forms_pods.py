# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Pod forms."""

__all__ = [
    "PodForm",
    ]

from django import forms
from django.core.exceptions import ValidationError
from maasserver.clusterrpc import driver_parameters
from maasserver.clusterrpc.driver_parameters import (
    get_driver_parameters_from_json,
)
from maasserver.clusterrpc.pods import (
    discover_pod,
    get_best_discovered_result,
)
from maasserver.enum import BMC_TYPE
from maasserver.exceptions import PodProblem
from maasserver.forms import MAASModelForm
from maasserver.models import (
    BMC,
    BMCRoutableRackControllerRelationship,
    Pod,
    RackController,
)
from maasserver.utils.forms import set_form_error
from provisioningserver.drivers import SETTING_SCOPE


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
        power_type = self.cleaned_data['type']
        # Set power_parameters to the generated param_fields.
        power_parameters = {
            param_name: self.cleaned_data[param_name]
            for param_name in self.param_fields.keys()
            if param_name in self.cleaned_data
        }

        # When the Pod is new try to get a BMC of the same type and parameters
        # to convert the BMC to a new Pod. When the Pod is not new the form
        # will use the already existing pod instance to update those fields.
        # If updating the fields causes a duplicate BMC then a validation erorr
        # will be raised from the model level.
        if self.is_new:
            bmc = BMC.objects.filter(
                power_type=power_type,
                power_parameters=power_parameters).first()
            if bmc is not None:
                if bmc.bmc_type == BMC_TYPE.BMC:
                    # Convert the BMC to a Pod and set as the instance for
                    # the PodForm.
                    bmc.bmc_type = BMC_TYPE.POD
                    self.instance = bmc.as_pod()
                else:
                    # Pod already exists with the same power_type and
                    # parameters.
                    raise ValidationError(
                        "Pod with type and parameters already exists.")

        self.instance = super(PodForm, self).save(commit=False)
        if not self.instance.name:
            self.instance.set_random_name()
        self.instance.power_type = power_type
        self.instance.power_parameters = power_parameters
        self.instance.save()
        return self.discover_and_sync_pod()

    def discover_and_sync_pod(self):
        """Discover and sync the pod information."""
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
                "No rack controllers connected to discover a pod.")
        self.instance.sync(discovered_pod, self.request.user)

        # Save which rack controllers can route and which cannot.
        discovered_rack_ids = [rack_id for rack_id, _ in discovered[0].items()]
        for rack_controller in RackController.objects.all():
            routable = rack_controller.system_id in discovered_rack_ids
            relation, created = (
                BMCRoutableRackControllerRelationship.objects.get_or_create(
                    bmc=self.instance.as_bmc(),
                    rack_controller=rack_controller,
                    defaults={'routable': routable}))
            if not created and relation.routable != routable:
                relation.routable = routable
                relation.save()
        return self.instance
