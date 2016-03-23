# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP snippets form."""

__all__ = [
    "DHCPSnippetForm",
]

from django import forms
from django.core.exceptions import ValidationError
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
    VersionedTextFile,
)


class DHCPSnippetForm(MAASModelForm):
    """DHCP snippet creation/edition form."""

    name = forms.CharField(
        label="Name", required=False, help_text=(
            "The name of the DHCP snippet."))

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

    def __init__(self, *args, **kwargs):
        # value is a required forign key to a VersionedTextFile object. When
        # creating a new DHCPSnipper first create the VersionedText object.
        # Create the instance here as super().__init__() doesn't pass the
        # required value field.
        if kwargs.get('instance') is None:
            name = kwargs['data'].get('name')
            if name is None:
                raise ValidationError("DHCP snippet requires a name.")
            value_data = kwargs['data'].get('value')
            if value_data is None:
                raise ValidationError("DHCP snippet requires a value.")
            value = VersionedTextFile.objects.create(data=value_data)
            kwargs['instance'] = DHCPSnippet.objects.create(
                name=name, value=value)
            # Set the data value to the newly created VerionedTextFile. This
            # tells VersionedTextFileField that it doesn't need todo anything.
            kwargs['data']['value'] = value
        super().__init__(*args, **kwargs)
        self.fields['value'] = VersionedTextFileField(
            label="DHCP Snippet", required=False, help_text="The DHCP Snippet",
            initial=kwargs['instance'].value)
        self.initial['value'] = self.instance.value.data
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
