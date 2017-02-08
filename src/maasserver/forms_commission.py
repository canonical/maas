# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Commission form."""

__all__ = [
    "CommissionForm",
]

from django.core.exceptions import ValidationError
from django.forms import (
    BooleanField,
    Form,
    MultipleChoiceField,
)
from django.http import QueryDict
from maasserver.node_action import compile_node_actions
from metadataserver.enum import SCRIPT_TYPE
from metadataserver.models import Script


class CommissionForm(Form):
    """Commission form."""

    enable_ssh = BooleanField(required=False, initial=False)
    skip_networking = BooleanField(required=False, initial=False)
    skip_storage = BooleanField(required=False, initial=False)

    def _set_up_script_fields(self):
        choices = {
            SCRIPT_TYPE.COMMISSIONING: [],
            SCRIPT_TYPE.TESTING: [('none', 'none')],
        }
        for script in Script.objects.all():
            for script_type, script_choices in choices.items():
                if script.script_type == script_type:
                    script_choices.append((script.name, script.name))
                    for tag in script.tags:
                        script_choices.append((tag, tag))
        self.fields['commissioning_scripts'] = MultipleChoiceField(
            required=False, initial=None,
            choices=choices[SCRIPT_TYPE.COMMISSIONING])
        self.fields['testing_scripts'] = MultipleChoiceField(
            required=False, initial=None, choices=choices[SCRIPT_TYPE.TESTING])

    def __init__(self, instance, user, data={}, **kwargs):
        super().__init__(data=data, **kwargs)
        self.instance = instance
        self.user = user
        # If a string was given convert into a list for validation and use.
        for script_field in ['commissioning_scripts', 'testing_scripts']:
            value = data.get(script_field)
            if value is None:
                continue
            if isinstance(value, str):
                if isinstance(data, QueryDict):
                    # QueryDict must have its value updated using setlist
                    # otherwise it puts the set value inside a list.
                    data.setlist(script_field, value.split(','))
                else:
                    data[script_field] = value.split(',')
        self._set_up_script_fields()

    def _get_node_action(self):
        actions = compile_node_actions(self.instance, self.user)
        return actions.get("commission")

    def clean(self):
        action = self._get_node_action()
        if action is None:
            raise ValidationError(
                "Commission is not available because of the current state "
                "of the node.")
        return super().clean()

    def save(self):
        enable_ssh = self.cleaned_data.get("enable_ssh", False)
        skip_networking = self.cleaned_data.get("skip_networking", False)
        skip_storage = self.cleaned_data.get("skip_storage", False)
        commissioning_scripts = self.cleaned_data.get("commissioning_scripts")
        testing_scripts = self.cleaned_data.get("testing_scripts")
        self.instance.start_commissioning(
            self.user, enable_ssh, skip_networking, skip_storage,
            commissioning_scripts, testing_scripts)
        return self.instance
