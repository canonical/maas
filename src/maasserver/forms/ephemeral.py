# Copyright 2015-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Commission form."""


from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import (
    BooleanField,
    CharField,
    ChoiceField,
    DurationField,
    Form,
    MultipleChoiceField,
)
from django.http import QueryDict

from maasserver.enum import NODE_STATUS
from maasserver.models import Script
from maasserver.node_action import get_node_action
from maasserver.utils.forms import set_form_error
from metadataserver.enum import SCRIPT_TYPE


class TestForm(Form):
    """Test form."""

    enable_ssh = BooleanField(required=False, initial=False)

    def _get_storage_choices(self):
        choices = [("all", "all")]
        for bd in self.instance.physicalblockdevice_set.all():
            choices.append((bd.id, bd.id))
            choices.append((bd.name, bd.name))
            choices.append((bd.model, bd.model))
            choices.append((bd.serial, bd.serial))
            model_serial = f"{bd.model}:{bd.serial}"
            choices.append((model_serial, model_serial))
            for tag in bd.tags:
                choices.append((tag, tag))
        return choices

    def _get_interface_choices(self):
        choices = [("all", "all")]
        for interface in self.instance.current_config.interface_set.filter(
            children_relationships=None
        ):
            choices.append((interface.id, interface.id))
            choices.append((interface.name, interface.name))
            mac = str(interface.mac_address)
            choices.append((mac, mac))
            choices.append((interface.vendor, interface.vendor))
            choices.append((interface.product, interface.product))
            vendor_product = f"{interface.vendor}:{interface.product}"
            choices.append((vendor_product, vendor_product))
            for tag in interface.tags:
                choices.append((tag, tag))
        return choices

    def _set_up_parameter_fields(self, scripts):
        storage_choices = None
        interface_choices = None
        for script in scripts:
            for pname, value in script.parameters.items():
                ptype = value.get("type")
                combined_name = f"{script.name}_{pname}"
                if ptype == "storage":
                    if storage_choices is None:
                        storage_choices = self._get_storage_choices()
                    self.fields[combined_name] = ChoiceField(
                        required=False, initial=None, choices=storage_choices
                    )
                    if pname not in self.fields:
                        self.fields[pname] = ChoiceField(
                            required=False,
                            initial=None,
                            choices=storage_choices,
                        )
                elif ptype == "interface":
                    if interface_choices is None:
                        interface_choices = self._get_interface_choices()
                    self.fields[combined_name] = ChoiceField(
                        required=False, initial=None, choices=interface_choices
                    )
                    if pname not in self.fields:
                        self.fields[pname] = ChoiceField(
                            required=False,
                            initial=None,
                            choices=interface_choices,
                        )
                elif ptype == "runtime":
                    self.fields[combined_name] = DurationField(
                        required=False, initial=None
                    )
                    if pname not in self.fields:
                        self.fields[pname] = DurationField(
                            required=False, initial=None
                        )
                elif ptype in ["url", "string", "password"]:
                    self.fields[combined_name] = CharField(
                        required=False, initial=None
                    )
                    if pname not in self.fields:
                        self.fields[pname] = CharField(
                            required=False, initial=None
                        )
                elif ptype == "boolean":
                    self.fields[combined_name] = BooleanField(
                        required=False, initial=None
                    )
                    if pname not in self.fields:
                        self.fields[pname] = BooleanField(
                            required=False, initial=None
                        )
                elif ptype == "choice":
                    # Support a Django choice list or a string list
                    choices = [
                        set(choice)
                        if isinstance(choice, list)
                        or isinstance(choice, set)
                        or isinstance(choice, tuple)
                        else (choice, choice)
                        for choice in value.get("choices", [])
                    ]
                    self.fields[combined_name] = ChoiceField(
                        required=False, initial=None, choices=choices
                    )
                    if pname not in self.fields:
                        self.fields[pname] = ChoiceField(
                            required=False, initial=None, choices=choices
                        )

    def _set_up_script_fields(self):
        testing_scripts = self.data.get("testing_scripts")
        if testing_scripts is not None and isinstance(testing_scripts, str):
            if isinstance(self.data, QueryDict):
                # QueryDict must have its value updated using setlist otherwise
                # it puts the set value inside a list.
                self.data.setlist(
                    "testing_scripts", testing_scripts.split(",")
                )
            else:
                self.data["testing_scripts"] = testing_scripts.split(",")

        choices = []
        scripts = Script.objects.filter(script_type=SCRIPT_TYPE.TESTING)
        for script in scripts:
            if script.script_type == SCRIPT_TYPE.TESTING:
                choices.append((script.name, script.name))
                for tag in script.tags:
                    choices.append((tag, tag))

        self.fields["testing_scripts"] = MultipleChoiceField(
            required=False, initial=None, choices=choices
        )
        self._set_up_parameter_fields(scripts)

    def __init__(self, instance, user, data=None, **kwargs):
        data = {} if data is None else data.copy()
        super().__init__(data=data, **kwargs)
        self.instance = instance
        self.user = user
        self._name = "test"
        self._display = "Test"
        self._set_up_script_fields()

    def clean(self):
        action = get_node_action(self.instance, self._name, self.user)
        if action is None:
            raise ValidationError(
                "%s is not available because of the current state of the node."
                % self._display
            )
        return super().clean()

    def is_valid(self):
        valid = super().is_valid()
        if (
            not self.instance.is_machine
            or self.instance.status == NODE_STATUS.DEPLOYED
        ):
            testing_scripts = self.cleaned_data.get("testing_scripts")
            if testing_scripts is None:
                return valid
            qs = Script.objects.filter(
                Q(name__in=testing_scripts) | Q(tags__overlap=testing_scripts),
                destructive=True,
            )
            if qs.exists():
                set_form_error(
                    self,
                    "testing_scripts",
                    "Destructive tests may only be run on undeployed machines.",
                )
                valid = False
        return valid

    def _get_script_param_dict(self, scripts):
        params = {}
        script_names = []
        ids = []
        for script in scripts:
            if script.isdigit():
                ids.append(int(script))
            else:
                script_names.append(script)
        qs = Script.objects.filter(
            Q(name__in=scripts) | Q(tags__overlap=scripts) | Q(id__in=ids)
        )
        for name, value in self.cleaned_data.items():
            if name in [
                "enable_ssh",
                "testing_scripts",
                "commissioning_scripts",
                "skip_bmc_config",
                "skip_networking",
                "skip_storage",
            ]:
                continue
            if not value:
                continue
            # Check if the parameter is for a particular script
            script_param = False
            for script in qs:
                if script.name in name:
                    if script.name not in params:
                        params[script.name] = {}
                    param = name.replace(script.name, "").strip("_-")
                    if isinstance(value, timedelta):
                        params[script.name][param] = int(value.total_seconds())
                    else:
                        params[script.name][param] = value
                    script_param = True
            # If its not for a particular script pass the parameter to all
            # scripts that support it.
            if not script_param:
                for script in qs:
                    if name in script.parameters and name not in params.get(
                        script.name, {}
                    ):
                        if script.name not in params:
                            params[script.name] = {}
                        if isinstance(value, timedelta):
                            params[script.name][name] = int(
                                value.total_seconds()
                            )
                        else:
                            params[script.name][name] = value
        return params

    def save(self):
        enable_ssh = self.cleaned_data.get("enable_ssh", False)
        testing_scripts = self.cleaned_data.get("testing_scripts")
        self.instance.start_testing(
            self.user,
            enable_ssh,
            testing_scripts,
            self._get_script_param_dict(testing_scripts),
        )
        return self.instance


class CommissionForm(TestForm):
    """Commission form."""

    skip_bmc_config = BooleanField(required=False, initial=False)
    skip_networking = BooleanField(required=False, initial=False)
    skip_storage = BooleanField(required=False, initial=False)

    def _set_up_script_fields(self):
        # If a string was given convert into a list for validation and use.
        for script_field in ["commissioning_scripts", "testing_scripts"]:
            value = self.data.get(script_field)
            if value is not None and isinstance(value, str):
                if isinstance(self.data, QueryDict):
                    # QueryDict must have its value updated using setlist
                    # otherwise it puts the set value inside a list.
                    self.data.setlist(script_field, value.split(","))
                else:
                    self.data[script_field] = value.split(",")

        choices = {
            SCRIPT_TYPE.COMMISSIONING: [("none", "none")],
            SCRIPT_TYPE.TESTING: [("none", "none")],
        }
        scripts = Script.objects.all()
        for script in scripts:
            for script_type, script_choices in choices.items():
                if script.script_type == script_type:
                    script_choices.append((script.name, script.name))
                    for tag in script.tags:
                        script_choices.append((tag, tag))

        self.fields["commissioning_scripts"] = MultipleChoiceField(
            required=False,
            initial=None,
            choices=choices[SCRIPT_TYPE.COMMISSIONING],
        )
        self.fields["testing_scripts"] = MultipleChoiceField(
            required=False, initial=None, choices=choices[SCRIPT_TYPE.TESTING]
        )
        self._set_up_parameter_fields(scripts)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name = "commission"
        self._display = "Commission"

    def save(self):
        enable_ssh = self.cleaned_data.get("enable_ssh", False)
        skip_bmc_config = self.cleaned_data.get("skip_bmc_config", False)
        skip_networking = self.cleaned_data.get("skip_networking", False)
        skip_storage = self.cleaned_data.get("skip_storage", False)
        commissioning_scripts = self.cleaned_data.get("commissioning_scripts")
        testing_scripts = self.cleaned_data.get("testing_scripts")
        self.instance.start_commissioning(
            self.user,
            enable_ssh,
            skip_bmc_config,
            skip_networking,
            skip_storage,
            commissioning_scripts,
            testing_scripts,
            self._get_script_param_dict(
                commissioning_scripts + testing_scripts
            ),
        )
        return self.instance
