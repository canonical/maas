# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Commission form."""

__all__ = [
    "CommissionForm",
]
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import (
    BooleanField,
    Form,
    MultipleChoiceField,
)
from django.http import QueryDict
from maasserver.enum import NODE_STATUS
from maasserver.node_action import compile_node_actions
from maasserver.utils.forms import set_form_error
from metadataserver.enum import SCRIPT_TYPE
from metadataserver.models import Script


class TestForm(Form):
    """Test form."""
    enable_ssh = BooleanField(required=False, initial=False)

    def _set_up_script_fields(self):
        testing_scripts = self.data.get('testing_scripts')
        if testing_scripts is not None and isinstance(testing_scripts, str):
            if isinstance(self.data, QueryDict):
                # QueryDict must have its value updated using setlist otherwise
                # it puts the set value inside a list.
                self.data.setlist(
                    'testing_scripts', testing_scripts.split(','))
            else:
                self.data['testing_scripts'] = testing_scripts.split(',')

        choices = []
        for script in Script.objects.all():
            if script.script_type == SCRIPT_TYPE.TESTING:
                choices.append((script.name, script.name))
                for tag in script.tags:
                    choices.append((tag, tag))

        self.fields['testing_scripts'] = MultipleChoiceField(
            required=False, initial=None, choices=choices)

    def __init__(self, instance, user, data={}, **kwargs):
        super().__init__(data=data, **kwargs)
        self._set_up_script_fields()
        self.instance = instance
        self.user = user
        self._name = 'test'
        self._display = 'Test'

    def clean(self):
        actions = compile_node_actions(self.instance, self.user)
        action = actions.get(self._name)
        if action is None:
            raise ValidationError(
                "%s is not available because of the current state of the node."
                % self._display)
        return super().clean()

    def is_valid(self):
        valid = super().is_valid()
        if (not self.instance.is_machine or
                self.instance.status == NODE_STATUS.DEPLOYED):
            testing_scripts = self.cleaned_data.get("testing_scripts")
            if testing_scripts is None:
                return valid
            qs = Script.objects.filter(
                Q(name__in=testing_scripts) | Q(tags__overlap=testing_scripts),
                destructive=True)
            if qs.exists():
                set_form_error(
                    self, "testing_scripts",
                    "Destructive tests may only be run on undeployed machines."
                )
                valid = False
        return valid

    def save(self):
        enable_ssh = self.cleaned_data.get("enable_ssh", False)
        testing_scripts = self.cleaned_data.get("testing_scripts")
        self.instance.start_testing(self.user, enable_ssh, testing_scripts)
        return self.instance


class CommissionForm(TestForm):
    """Commission form."""

    skip_networking = BooleanField(required=False, initial=False)
    skip_storage = BooleanField(required=False, initial=False)

    def _set_up_script_fields(self):
        # If a string was given convert into a list for validation and use.
        for script_field in ['commissioning_scripts', 'testing_scripts']:
            value = self.data.get(script_field)
            if value is not None and isinstance(value, str):
                if isinstance(self.data, QueryDict):
                    # QueryDict must have its value updated using setlist
                    # otherwise it puts the set value inside a list.
                    self.data.setlist(script_field, value.split(','))
                else:
                    self.data[script_field] = value.split(',')

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name = 'commission'
        self._display = 'Commission'

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
