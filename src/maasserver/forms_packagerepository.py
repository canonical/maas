# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Package Repositories form."""

__all__ = [
    "PackageRepositoryForm",
]

from django import forms
from django.core.exceptions import ValidationError
from maasserver.fields import URLOrPPAFormField
from maasserver.forms import (
    MAASModelForm,
    UnconstrainedMultipleChoiceField,
)
from maasserver.models import PackageRepository


class PackageRepositoryForm(MAASModelForm):
    """Package Repository creation/edition form."""

    class Meta:
        model = PackageRepository
        fields = (
            'name',
            'url',
            'distributions',
            'disabled_pockets',
            'components',
            'arches',
            'key',
            'enabled',
            )

    name = forms.CharField(
        label="Name", required=True, help_text=(
            "The name of the Package Repository."))

    url = URLOrPPAFormField(
        label="Package Repository URL",
        required=True, help_text="The Package Repository URL")

    # Use UnconstrainedMultipleChoiceField fields for multiple-choices
    # fields instead of the default (djorm-ext-pgarray's ArrayFormField):
    # ArrayFormField deals with comma-separated lists and here we want to
    # handle multiple-values submissions.
    distributions = UnconstrainedMultipleChoiceField(label="Distribution list")

    disabled_pockets = UnconstrainedMultipleChoiceField(
        label="Disabled Pocket list")

    components = UnconstrainedMultipleChoiceField(label="Component list")

    arches = UnconstrainedMultipleChoiceField(label="Architecture list")

    key = forms.CharField(
        label="Key", required=False, help_text=(
            "The key used to authenticate the Package Repository."))

    enabled = forms.BooleanField(
        label="Enabled", required=False, help_text=(
            "Whether or not the Package Repository is enabled."))

    def __init__(self, data=None, instance=None, request=None, **kwargs):
        super().__init__(data=data, instance=instance, **kwargs)
        if self.instance.id is None:
            self.initial['enabled'] = True
        else:
            self.fields['url'].initial = self.instance.url

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.default and not cleaned_data.get('enabled', False):
            raise ValidationError("Default repositories may not be disabled.")

    def clean_arches(self):
        arches = []
        for value in self.cleaned_data.get('arches', []):
            arches.extend([s.strip() for s in value.split(',')])
        known_arches = set(PackageRepository.objects.get_known_architectures())
        for value in arches:
            if value not in known_arches:
                raise ValidationError(
                    "'%s' is not a valid architecture. Known architectures: "
                    "%s" % (value, ", ".join(sorted(known_arches))))
        # If no arches provided, use MAIN_ARCHES.
        if len(arches) == 0:
            arches = PackageRepository.MAIN_ARCHES
        return arches

    def clean_distributions(self):
        values = []
        for value in self.cleaned_data.get('distributions', []):
            values.extend([s.strip() for s in value.split(',')])
        return values

    def clean_disabled_pockets(self):
        values = []
        for value in self.cleaned_data.get('disabled_pockets', []):
            values.extend([s.strip() for s in value.split(',')])
        return values

    def clean_components(self):
        values = []
        for value in self.cleaned_data.get('components', []):
            values.extend([s.strip() for s in value.split(',')])
        return values
