# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP snippets form."""

__all__ = [
    "DHCPSnippetForm",
]

from django import forms
from django.core.exceptions import ValidationError
from maasserver.dhcp import validate_dhcp_config
from maasserver.fields import (
    NodeChoiceField,
    SpecifierOrModelChoiceField,
    VersionedTextFileField,
)
from maasserver.forms import MAASModelForm
from maasserver.models import (
    DHCPSnippet,
    Node,
    Subnet,
)
from maasserver.utils.forms import set_form_error


class DHCPSnippetForm(MAASModelForm):
    """DHCP snippet creation/edition form."""

    name = forms.CharField(
        label="Name", required=False, help_text=(
            "The name of the DHCP snippet."))

    value = VersionedTextFileField(
        label="DHCP Snippet", required=False, help_text="The DHCP Snippet")

    description = forms.CharField(
        label="Description", required=False, help_text=(
            "The description of what the DHCP snippet does."))

    enabled = forms.BooleanField(
        label="Enabled", required=False, help_text=(
            "Whether or not the DHCP snippet is enabled."))

    node = NodeChoiceField(
        label="Node", queryset=Node.objects.all(), required=False,
        initial=None, help_text=(
            "The node which the DHCP snippet is for."))

    subnet = SpecifierOrModelChoiceField(
        label="Subnet", queryset=Subnet.objects.all(), required=False,
        help_text="The subnet which the DHCP snippet is for.")

    global_snippet = forms.BooleanField(
        label="Global DHCP Snippet", required=False, help_text=(
            "Set the DHCP snippet to be global, removes links to nodes or "
            "subnets"))

    class Meta:
        model = DHCPSnippet
        fields = (
            'name',
            'value',
            'description',
            'enabled',
            'node',
            'subnet',
            'global_snippet',
            )

    def __init__(self, data=None, instance=None, request=None, **kwargs):
        super().__init__(data=data, instance=instance, **kwargs)
        if self.instance.id is None:
            if data.get('name') is None:
                raise ValidationError("DHCP snippet requires a name.")
            elif data.get('value') is None:
                raise ValidationError("DHCP snippet requires a value.")
        else:
            self.fields['value'].initial = self.instance.value
        if self.instance.node is not None:
            self.initial['node'] = self.instance.node.system_id

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('global_snippet', False):
            cleaned_data['node'] = None
            self.instance.node = None
            cleaned_data['subnet'] = None
            self.instance.subnet = None
        return cleaned_data

    def is_valid(self):
        valid = super().is_valid()
        if valid:
            # Often the first error can cause cascading errors. Showing all of
            # these errors can be confusing so only show the first if there is
            # one.
            first_error = None
            for error in validate_dhcp_config(self.instance):
                valid = False
                if first_error is None:
                    first_error = error
                else:
                    if error['line_num'] < first_error['line_num']:
                        first_error = error
            if first_error is not None:
                set_form_error(self, 'value', first_error['error'])

        # If the DHCPSnippet isn't valid cleanup the value
        if not valid:
            self.instance.value.delete()
        return valid
