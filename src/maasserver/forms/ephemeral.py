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


class ScriptForm(Form):
    name = "script"
    display = "Script"
    # tuples of supported parameters names for scripts, with their script type
    # and whether "none" can be passed as parameter
    script_fields_details: tuple[tuple[str, int, bool]] = ()

    _scripts: list[Script]

    def __init__(self, instance, user, data=None, **kwargs):
        # ensure the data field is a dict, since QueryDict is immutable
        data = data.copy() if data else {}
        super().__init__(data=data, **kwargs)
        self.instance = instance
        self.user = user
        self._scripts = list(
            Script.objects.filter(
                script_type__in=[
                    entry[1] for entry in self.script_fields_details
                ]
            )
        )
        self._set_up_script_fields()
        self._set_up_parameter_fields()

    def clean(self):
        action = get_node_action(self.instance, self.name, self.user)
        if action is None:
            raise ValidationError(
                f"{self.display} is not available because "
                "of the current state of the node."
            )
        return super().clean()

    def _clean_fields(self):
        # before validating fields, split values for the list of scripts
        for param, script_type, _ in self.script_fields_details:
            scripts = self.data.get(param)
            if scripts is not None and isinstance(scripts, str):
                if isinstance(self.data, QueryDict):
                    # QueryDict must have its value updated using setlist otherwise
                    # it puts the set value inside a list.
                    self.data.setlist(param, scripts.split(","))
                else:
                    self.data[param] = scripts.split(",")
        return super()._clean_fields()

    def get_script_param_dict(self, names):
        params = {}
        scripts = list(
            Script.objects.filter(Q(name__in=names) | Q(tags__overlap=names))
        )
        for name, value in self.cleaned_data.items():
            if not value:
                continue
            # Check if the parameter is for a particular script
            script_param = False
            for script in scripts:
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
                for script in scripts:
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

    def _set_up_script_fields(self):
        for param, script_type, allow_none in self.script_fields_details:
            choices = []
            if allow_none:
                choices.append(("none", "none"))
            for script in self._scripts:
                if script.script_type == script_type:
                    choices.append((script.name, script.name))
                    choices.extend((tag, tag) for tag in script.tags)

            self.fields[param] = MultipleChoiceField(
                required=False, initial=None, choices=choices
            )

    def _set_up_parameter_fields(self):
        storage_choices = None
        interface_choices = None
        for script in self._scripts:
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
                        if isinstance(choice, (list, set, tuple))
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

    def _get_storage_choices(self):
        choices = [("all", "all")]
        for bd in self.instance.physicalblockdevice_set.all():
            model_serial = f"{bd.model}:{bd.serial}"
            choices.extend(
                (
                    (bd.id, bd.id),
                    (bd.name, bd.name),
                    (bd.model, bd.model),
                    (bd.serial, bd.serial),
                    (model_serial, model_serial),
                )
            )
            choices.extend((tag, tag) for tag in bd.tags)
        return choices

    def _get_interface_choices(self):
        choices = [("all", "all")]
        for interface in self.instance.current_config.interface_set.filter(
            children_relationships=None
        ):
            mac = str(interface.mac_address)
            vendor_product = f"{interface.vendor}:{interface.product}"
            choices.extend(
                (
                    (interface.id, interface.id),
                    (interface.name, interface.name),
                    (mac, mac),
                    (interface.vendor, interface.vendor),
                    (interface.product, interface.product),
                    (vendor_product, vendor_product),
                )
            )
            choices.extend((tag, tag) for tag in interface.tags)
        return choices


class TestForm(ScriptForm):
    """Test form."""

    name = "test"
    display = "Test"
    script_fields_details = (("testing_scripts", SCRIPT_TYPE.TESTING, False),)

    enable_ssh = BooleanField(required=False, initial=False)

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

    def save(self):
        enable_ssh = self.cleaned_data.get("enable_ssh", False)
        testing_scripts = self.cleaned_data.get("testing_scripts")
        params = self.get_script_param_dict(testing_scripts)
        self.instance.start_testing(
            self.user,
            enable_ssh,
            testing_scripts,
            params,
        )
        return self.instance


class CommissionForm(TestForm):
    """Commission form."""

    name = "commission"
    display = "Commission"
    script_fields_details = (
        ("commissioning_scripts", SCRIPT_TYPE.COMMISSIONING, False),
        ("testing_scripts", SCRIPT_TYPE.TESTING, True),
    )

    skip_bmc_config = BooleanField(required=False, initial=False)
    skip_networking = BooleanField(required=False, initial=False)
    skip_storage = BooleanField(required=False, initial=False)

    def save(self):
        enable_ssh = self.cleaned_data.get("enable_ssh", False)
        skip_bmc_config = self.cleaned_data.get("skip_bmc_config", False)
        skip_networking = self.cleaned_data.get("skip_networking", False)
        skip_storage = self.cleaned_data.get("skip_storage", False)
        commissioning_scripts = self.cleaned_data.get("commissioning_scripts")
        testing_scripts = self.cleaned_data.get("testing_scripts")
        params = self.get_script_param_dict(
            commissioning_scripts + testing_scripts
        )
        self.instance.start_commissioning(
            self.user,
            enable_ssh,
            skip_bmc_config,
            skip_networking,
            skip_storage,
            commissioning_scripts,
            testing_scripts,
            params,
        )
        return self.instance
