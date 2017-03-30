# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Script form."""

__all__ = [
    "ScriptForm",
]
from datetime import timedelta

from django.forms import (
    CharField,
    DurationField,
    ModelForm,
)
from maasserver.fields import VersionedTextFileField
from maasserver.utils.forms import set_form_error
from metadataserver.enum import SCRIPT_TYPE
from metadataserver.models import Script


class ScriptForm(ModelForm):

    script_type = CharField(
        label='Script type', required=False, help_text='Script type',
        initial=str(SCRIPT_TYPE.TESTING))

    timeout = DurationField(
        label='Timeout', required=False,
        help_text='Timeout', initial=timedelta(0))

    script = VersionedTextFileField(label="Script", help_text="Script content")

    comment = CharField(
        label='Comment', required=False, help_text='Description of change',
        initial='')

    class Meta:
        model = Script
        fields = (
            'name',
            'title',
            'description',
            'tags',
            'script_type',
            'timeout',
            'destructive',
            'script',
        )

    def __init__(self, instance=None, **kwargs):
        super().__init__(instance=instance, **kwargs)
        if instance is None:
            for field in ['name', 'script']:
                self.fields[field].required = True
            script_data_key = 'data'
        else:
            for field in ['name', 'script']:
                self.fields[field].required = False
            self.fields['script'].initial = instance.script
            script_data_key = 'new_data'
        if 'comment' in self.data and 'script' in self.data:
            script_data = {
                'comment': self.data.get('comment'),
                script_data_key: self.data.get('script'),
            }
            self.data['script'] = script_data
            self.data.pop('comment')

    def clean(self):
        cleaned_data = super().clean()
        script_type = cleaned_data['script_type']
        if script_type.isdigit():
            cleaned_data['script_type'] = int(script_type)
        elif script_type in ['test', 'testing']:
            cleaned_data['script_type'] = SCRIPT_TYPE.TESTING
        elif script_type in ['commission', 'commissioning']:
            cleaned_data['script_type'] = SCRIPT_TYPE.COMMISSIONING
        elif script_type == '':
            cleaned_data['script_type'] = self.instance.script_type
        else:
            set_form_error(
                self, 'script_type',
                'Must be %d, test, testing, %d, commission, or commissioning.'
                % (SCRIPT_TYPE.TESTING, SCRIPT_TYPE.COMMISSIONING))
        # If a field wasn't passed in keep the old values when updating.
        if self.instance.id is not None:
            for field in self._meta.fields:
                if field not in self.data:
                    cleaned_data[field] = getattr(self.instance, field)
        return cleaned_data

    def is_valid(self):
        valid = super().is_valid()

        if valid and self.instance.default:
            for field in self.Meta.fields:
                if field in ['tags', 'timeout']:
                    continue
                if field in self.data:
                    set_form_error(
                        self, field,
                        'Not allowed to change on default scripts.')
                    valid = False

        name = self.data.get('name')
        if name is not None and name.lower() == 'none':
            set_form_error(self, 'name', '"none" is a reserved name.')
            valid = False

        # The name can't be a digit as MAAS allows scripts to be selected by
        # id.
        if name is not None and name.isdigit():
            set_form_error(self, 'name', 'Cannot be a number.')
            valid = False

        # If comment and script exist __init__ combines both fields into a dict
        # to pass to VersionedTextFileField.
        if 'comment' in self.data:
            set_form_error(
                self, 'comment',
                '"comment" may only be used when specifying a "script" '
                'as well.')
            valid = False

        if (not valid and self.instance.script_id is not None and
                self.initial.get('script') != self.instance.script_id):
            # If form validation failed cleanup any new VersionedTextFile
            # created by the VersionedTextFileField.
            self.instance.script.delete()
        return valid
