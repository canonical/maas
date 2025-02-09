# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Package Repositories form."""

from django import forms
from django.core.exceptions import ValidationError

from maasserver.audit import create_audit_event
from maasserver.fields import URLOrPPAFormField
from maasserver.forms import MAASModelForm, UnconstrainedMultipleChoiceField
from maasserver.models import PackageRepository
from provisioningserver.events import EVENT_TYPES


class PackageRepositoryForm(MAASModelForm):
    """Package Repository creation/edition form."""

    class Meta:
        model = PackageRepository
        fields = (
            "name",
            "url",
            "distributions",
            "disabled_pockets",
            "disabled_components",
            "disable_sources",
            "components",
            "arches",
            "key",
            "enabled",
        )

    name = forms.CharField(
        label="Name",
        required=True,
        help_text="The name of the Package Repository.",
    )

    url = URLOrPPAFormField(
        label="Package Repository URL",
        required=True,
        help_text="The Package Repository URL",
    )

    # Use UnconstrainedMultipleChoiceField fields for multiple-choices
    # fields instead of the default as we want to handle
    # multiple-values submissions.
    distributions = UnconstrainedMultipleChoiceField(label="Distribution list")

    disabled_pockets = UnconstrainedMultipleChoiceField(
        label="Disabled Pocket list"
    )

    disabled_components = UnconstrainedMultipleChoiceField(
        label="Disabled Component list"
    )

    disable_sources = forms.BooleanField(
        label="Disable Sources",
        required=False,
        help_text="Whether or not deb-src lines are disabled.",
    )

    components = UnconstrainedMultipleChoiceField(label="Component list")

    arches = UnconstrainedMultipleChoiceField(label="Architecture list")

    key = forms.CharField(
        label="Key",
        required=False,
        help_text="The key used to authenticate the Package Repository.",
    )

    enabled = forms.BooleanField(
        label="Enabled",
        required=False,
        help_text="Whether or not the Package Repository is enabled.",
    )

    def __init__(self, data=None, instance=None, request=None, **kwargs):
        super().__init__(data=data, instance=instance, **kwargs)
        if self.instance.id is None:
            self.initial["enabled"] = True
        else:
            self.fields["url"].initial = self.instance.url

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.default and not cleaned_data.get("enabled", False):
            raise ValidationError("Default repositories may not be disabled.")

    def clean_arches(self):
        arches = []
        for value in self.cleaned_data.get("arches", []):
            arches.extend([s.strip() for s in value.split(",")])
        known_arches = set(PackageRepository.objects.get_known_architectures())
        for value in arches:
            if value not in known_arches:
                raise ValidationError(
                    "'%s' is not a valid architecture. Known architectures: "
                    "%s" % (value, ", ".join(sorted(known_arches)))
                )
        # If no arches provided, use PORTS_ARCHES for the ports archive,
        # MAIN_ARCHES as default fallback.
        if len(arches) == 0:
            if self.cleaned_data.get("name") == "ports_archive":
                arches = PackageRepository.PORTS_ARCHES
            else:
                arches = PackageRepository.MAIN_ARCHES
        return arches

    def clean_distributions(self):
        values = []
        for value in self.cleaned_data.get("distributions", []):
            values.extend([s.strip() for s in value.split(",")])
        return values

    def clean_disabled_pockets(self):
        values = []
        for value in self.cleaned_data.get("disabled_pockets", []):
            values.extend([s.strip() for s in value.split(",")])
        # This allows to reset the values of disabled_pockets if one of the
        # following is passed over the API:
        #   disabled_pockets=
        #   disabled_pockets=''
        #   disabled_pockets=None
        #   disabled_pockets=[]
        if values == [""] or values == ["None"] or values == ["[]"]:
            return []
        # Check that a valid pocket is being disable.
        for pocket in values:
            if pocket not in PackageRepository.POCKETS_TO_DISABLE:
                raise ValidationError(
                    "'%s' is not a valid Ubuntu archive pocket. You "
                    "can only disable %s."
                    % (pocket, PackageRepository.POCKETS_TO_DISABLE)
                )
        return values

    def clean_disabled_components(self):
        values = []
        for value in self.cleaned_data.get("disabled_components", []):
            values.extend([s.strip() for s in value.split(",")])
        # This allows to reset the values of disabled_components if one of the
        # following is passed over the API:
        #   disabled_components=
        #   disabled_components=''
        #   disabled_components=None
        #   disabled_components=[]
        if values == [""] or values == ["None"] or values == ["[]"]:
            return []
        if self.instance is not None and not self.instance.default and values:
            raise ValidationError(
                "This is a custom repository. Please update 'components' "
                "instead."
            )
        # Check that a valid component is being passed.
        for component in values:
            if component not in PackageRepository.COMPONENTS_TO_DISABLE:
                raise ValidationError(
                    "'%s' is not a valid Ubuntu archive component. You "
                    "can only disable %s."
                    % (component, PackageRepository.COMPONENTS_TO_DISABLE)
                )
        return values

    def clean_components(self):
        values = []
        for value in self.cleaned_data.get("components", []):
            values.extend([s.strip() for s in value.split(",")])
        if self.instance is not None and self.instance.default and values:
            raise ValidationError(
                "This is a default Ubuntu repository. Please update "
                "'disabled_components' instead."
            )
        return values

    def save(self, endpoint, request):
        package_repository = super().save()
        create_audit_event(
            EVENT_TYPES.SETTINGS,
            endpoint,
            request,
            None,
            description=(
                "%s package repository '%s'."
                % (
                    "Updated" if self.is_update else "Created",
                    package_repository.name,
                )
            ),
        )
        return package_repository
