# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Clone form."""


from django import forms
from django.contrib.postgres.forms.array import SimpleArrayField
from django.contrib.postgres.utils import prefix_validation_error
from django.core.exceptions import ValidationError

from maasserver.enum import NODE_STATUS
from maasserver.fields import NodeChoiceField
from maasserver.models import Machine
from maasserver.permissions import NodePermission


class CloneForm(forms.Form):
    """Clone storage/interface form."""

    source = NodeChoiceField(
        label="Source",
        queryset=Machine.objects.all(),
        required=True,
        initial=None,
        help_text="The source machine to clone from.",
    )

    destinations = SimpleArrayField(
        NodeChoiceField(queryset=Machine.objects.all()),
        label="Destinations",
        min_length=1,
        error_messages={
            "item_invalid": "Machine %(nth)s is invalid:",
            "is-source": "Source machine %(machine)s cannot be a destination machine.",
            "storage": "%(machine)s is invalid:",
            "networking": "%(machine)s is invalid:",
        },
        help_text="The destinations to clone to.",
    )

    storage = forms.BooleanField(
        label="Storage",
        required=False,
        help_text="Clone the storage configuration.",
    )

    interfaces = forms.BooleanField(
        label="Interfaces",
        required=False,
        help_text="Clone the interfaces configuration.",
    )

    def __init__(self, user, **kwargs):
        self.user = user
        super().__init__(**kwargs)
        self.fields["source"].queryset = Machine.objects.get_nodes(
            self.user, NodePermission.view
        )
        self.fields["destinations"].base_field.queryset = (
            Machine.objects.get_nodes(
                self.user,
                NodePermission.admin,
                from_nodes=Machine.objects.filter(
                    status__in={NODE_STATUS.READY, NODE_STATUS.FAILED_TESTING}
                ),
            )
        )

    def clean(self):
        """Validate that the form is valid and that the destinations can accept
        the storage and/or interfaces configuration from the source."""
        cleaned_data = super().clean()
        source = self.cleaned_data.get("source")
        if not source:
            # Django should be placing this automatically, but it does not
            # occur. So we force the setting of this error here.
            self.add_error("source", "This field is required.")
        destinations = self.cleaned_data.get("destinations")
        destination_field = self.fields["destinations"]
        storage = self.cleaned_data.get("storage", False)
        interfaces = self.cleaned_data.get("interfaces", False)
        if source and destinations:
            for dest in destinations:
                if source == dest:
                    error = ValidationError(
                        destination_field.error_messages["is-source"],
                        code="is-source",
                        params={
                            "machine": str(dest),
                            "system_id": dest.system_id,
                        },
                    )
                    self.add_error("destinations", error)
                else:
                    if storage:
                        try:
                            dest._get_storage_mapping_between_nodes(source)
                        except ValidationError as exc:
                            error = prefix_validation_error(
                                exc,
                                prefix=destination_field.error_messages[
                                    "storage"
                                ],
                                code="storage",
                                params={
                                    "machine": str(dest),
                                    "system_id": dest.system_id,
                                },
                            )
                            self.add_error("destinations", error)
                    if interfaces:
                        try:
                            dest._get_interface_mapping_between_nodes(source)
                        except ValidationError as exc:
                            error = prefix_validation_error(
                                exc,
                                prefix=destination_field.error_messages[
                                    "networking"
                                ],
                                code="networking",
                                params={
                                    "machine": str(dest),
                                    "system_id": dest.system_id,
                                },
                            )
                            self.add_error("destinations", error)
        if not storage and not interfaces:
            self.add_error(
                "__all__",
                ValidationError(
                    "Either storage or interfaces must be true.",
                    code="required",
                ),
            )
        return cleaned_data

    def strip_failed_destinations(self):
        """Remove destinations that have errors."""
        if "destinations" not in self.cleaned_data:
            submitted_destinations = self.data.get("destinations")
            # Don't try and manipulate empty submission
            if not submitted_destinations:
                return
            errors = self.errors.as_data()
            bogus_system_ids = {
                error.params["system_id"] for error in errors["destinations"]
            }
            return [
                dest
                for dest in submitted_destinations
                if dest not in bogus_system_ids
            ]

    def save(self):
        """Clone the storage and/or interfaces configuration to the
        destinations."""
        source = self.cleaned_data.get("source")
        destinations = self.cleaned_data.get("destinations", [])
        storage = self.cleaned_data.get("storage", False)
        interfaces = self.cleaned_data.get("interfaces", False)
        for dest in destinations:
            if storage:
                dest.set_storage_configuration_from_node(source)
            if interfaces:
                dest.set_networking_configuration_from_node(source)
