# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP snippets form."""

from django import forms

from maasserver.audit import create_audit_event
from maasserver.fields import (
    NodeChoiceField,
    SpecifierOrModelChoiceField,
    VersionedTextFileField,
)
from maasserver.forms import MAASModelForm
from maasserver.models import DHCPSnippet, IPRange, Node, Subnet
from provisioningserver.events import EVENT_TYPES


class DHCPSnippetForm(MAASModelForm):
    """DHCP snippet creation/edition form."""

    name = forms.CharField(
        label="Name", required=False, help_text="The name of the DHCP snippet."
    )

    value = VersionedTextFileField(
        label="DHCP Snippet", required=False, help_text="The DHCP Snippet"
    )

    description = forms.CharField(
        label="Description",
        required=False,
        help_text="The description of what the DHCP snippet does.",
    )

    enabled = forms.BooleanField(
        label="Enabled",
        required=False,
        help_text="Whether or not the DHCP snippet is enabled.",
    )

    node = NodeChoiceField(
        label="Node",
        queryset=Node.objects.all(),
        required=False,
        initial=None,
        help_text="The node which the DHCP snippet is for.",
    )

    subnet = SpecifierOrModelChoiceField(
        label="Subnet",
        queryset=Subnet.objects.all(),
        required=False,
        help_text="The subnet which the DHCP snippet is for.",
    )

    iprange = SpecifierOrModelChoiceField(
        label="IP Range",
        queryset=IPRange.objects.all(),
        required=False,
        initial=None,
        help_text="The iprange which the DHCP snippet is for.",
    )

    global_snippet = forms.BooleanField(
        label="Global DHCP Snippet",
        required=False,
        help_text=(
            "Set the DHCP snippet to be global, removes links to nodes or "
            "subnets"
        ),
    )

    class Meta:
        model = DHCPSnippet
        fields = (
            "name",
            "value",
            "description",
            "enabled",
            "node",
            "subnet",
            "iprange",
            "global_snippet",
        )

    def __init__(self, instance=None, request=None, **kwargs):
        super().__init__(instance=instance, **kwargs)
        if instance is None:
            for field in ["name", "value"]:
                self.fields[field].required = True
            self.initial["enabled"] = True
        else:
            self.fields["value"].initial = self.instance.value
        if instance is not None and instance.node is not None:
            self.initial["node"] = self.instance.node.system_id
        if instance is not None and instance.subnet is not None:
            self.fields["iprange"].queryset = IPRange.objects.filter(
                subnet=instance.subnet
            )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("global_snippet", False):
            cleaned_data["node"] = None
            self.instance.node = None
            cleaned_data["subnet"] = None
            self.instance.subnet = None
        elif (
            self.instance.subnet == cleaned_data.get("subnet")
            and cleaned_data.get("node") is not None
        ):
            cleaned_data["subnet"] = None
            self.instance.subnet = None
        elif (
            self.instance.node == cleaned_data.get("node")
            and cleaned_data.get("subnet") is not None
        ):
            cleaned_data["node"] = None
            self.instance.node = None
        return cleaned_data

    def is_valid(self):
        valid = super().is_valid()

        # If the DHCPSnippet isn't valid cleanup the value
        if not valid and self.initial.get("value") != self.instance.value_id:
            self.instance.value.delete()
        return valid

    def save(self, endpoint, request):
        dhcp_snippet = super().save()
        create_audit_event(
            EVENT_TYPES.SETTINGS,
            endpoint,
            request,
            None,
            description=(
                "%s DHCP snippet '%s'."
                % (
                    "Updated" if self.is_update else "Created",
                    dhcp_snippet.name,
                )
            ),
        )
        return dhcp_snippet
