# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""VMCluster forms."""

from django import forms

from maasserver.forms import MAASModelForm
from maasserver.models import DefaultResource, ResourcePool, VMCluster, Zone


class UpdateVMClusterForm(MAASModelForm):
    """Update VMCluster"""

    class Meta:
        model = VMCluster
        fields = [
            "name",
            "zone",
            "pool",
        ]

    name = forms.CharField(
        label="Name", required=False, help_text="The name of the vmcluster"
    )

    zone = forms.ModelChoiceField(
        label="Physical zone",
        required=False,
        initial=DefaultResource.objects.get_default_zone,
        queryset=Zone.objects.all(),
        to_field_name="name",
    )

    pool = forms.ModelChoiceField(
        label="Default pool of created machines",
        required=False,
        initial=lambda: ResourcePool.objects.get_default_resource_pool().name,
        queryset=ResourcePool.objects.all(),
        to_field_name="name",
    )

    def __init__(
        self, data=None, instance=None, request=None, user=None, **kwargs
    ):
        self.is_new = instance is None
        self.request = request
        self.user = user
        super().__init__(data=data, instance=instance, **kwargs)
        if data is None:
            data = {}
        if instance is not None:
            self.initial["zone"] = instance.zone.name
            self.initial["pool"] = (
                instance.pool.name if instance.pool is not None else ""
            )


class DeleteVMClusterForm(forms.Form):
    """Delete VMCluster"""

    decompose = forms.BooleanField(required=False, initial=False)
