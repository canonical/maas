# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""PackageRepository objects."""

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    CharField,
    Manager,
    QuerySet,
    TextField,
)

from maascommon.enums.package_repositories import (
    ComponentsToDisableEnum,
    KnownArchesEnum,
    KnownComponentsEnum,
    PocketsToDisableEnum,
)
from maasserver.fields import URLOrPPAField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin


class PackageRepositoryQueriesMixin(MAASQueriesMixin):
    def get_specifiers_q(self, specifiers, separator=":", **kwargs):
        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            "id": "__id",
            "name": "__name",
        }
        return super().get_specifiers_q(
            specifiers,
            specifier_types=specifier_types,
            separator=separator,
            **kwargs,
        )


class PackageRepositoryQuerySet(QuerySet, PackageRepositoryQueriesMixin):
    """Custom QuerySet which mixes in some additional queries specific to
    this object. This needs to be a mixin because an identical method is needed
    on both the Manager and all QuerySets which result from calling the
    manager.
    """


class PackageRepositoryManager(Manager, PackageRepositoryQueriesMixin):
    """Manager for `PackageRepository` class."""

    def get_queryset(self):
        return PackageRepositoryQuerySet(self.model, using=self._db)

    def get_object_or_404(self, specifiers):
        """Fetch a `PackageRepository` by its id. Raise exceptions if no
        `PackageRepository` with its id exists, or if the provided user does
        not have the required permission on this `PackageRepository`.

        :param specifiers: The interface specifier.
        :type specifiers: str
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        return self.get_object_by_specifiers_or_raise(specifiers)

    def get_known_architectures(self):
        return PackageRepository.KNOWN_ARCHES

    def get_pockets_to_disable(self):
        return PackageRepository.POCKETS_TO_DISABLE

    def get_components_to_disable(self):
        return PackageRepository.COMPONENTS_TO_DISABLE

    def get_default_archive(self, arch):
        return PackageRepository.objects.filter(
            arches__contains=[arch], enabled=True, default=True
        ).first()

    def get_additional_repositories(self, arch):
        return PackageRepository.objects.filter(
            arches__contains=[arch], enabled=True, default=False
        ).all()


class PackageRepository(CleanSave, TimestampedModel):
    """A `PackageRepository`."""

    MAIN_ARCHES = [KnownArchesEnum.AMD64.value, KnownArchesEnum.I386.value]
    PORTS_ARCHES = [
        KnownArchesEnum.ARMHF.value,
        KnownArchesEnum.ARM64.value,
        KnownArchesEnum.PPC64EL.value,
        KnownArchesEnum.S390X.value,
    ]
    KNOWN_ARCHES = MAIN_ARCHES + PORTS_ARCHES
    POCKETS_TO_DISABLE = [
        PocketsToDisableEnum.UPDATES.value,
        PocketsToDisableEnum.SECURITY.value,
        PocketsToDisableEnum.BACKPORTS.value,
    ]
    COMPONENTS_TO_DISABLE = [
        ComponentsToDisableEnum.RESTRICTED.value,
        ComponentsToDisableEnum.UNIVERSE.value,
        ComponentsToDisableEnum.MULTIVERSE.value,
    ]
    KNOWN_COMPONENTS = [
        KnownComponentsEnum.MAIN.value,
        KnownComponentsEnum.RESTRICTED.value,
        KnownComponentsEnum.UNIVERSE.value,
        KnownComponentsEnum.MULTIVERSE.value,
    ]

    objects = PackageRepositoryManager()

    name = CharField(max_length=41, unique=True, default="")

    url = URLOrPPAField(
        blank=False, help_text="The URL of the PackageRepository."
    )

    distributions = ArrayField(
        TextField(), blank=True, null=True, default=list
    )

    disabled_pockets = ArrayField(
        TextField(), blank=True, null=True, default=list
    )

    disabled_components = ArrayField(
        TextField(), blank=True, null=True, default=list
    )

    disable_sources = BooleanField(default=True)

    components = ArrayField(TextField(), blank=True, null=True, default=list)

    arches = ArrayField(TextField(), blank=True, null=True, default=list)

    key = TextField(blank=True, default="")

    default = BooleanField(default=False)

    enabled = BooleanField(default=True)

    def __str__(self):
        return f"{self.id} ({self.name})"

    @classmethod
    def get_main_archive_url(cls):
        return cls.get_main_archive().url

    @classmethod
    def get_main_archive(cls):
        return cls.objects.filter(
            arches__overlap=PackageRepository.MAIN_ARCHES,
            enabled=True,
            default=True,
        ).first()

    @classmethod
    def get_ports_archive_url(cls):
        return cls.get_ports_archive().url

    @classmethod
    def get_ports_archive(cls):
        return cls.objects.filter(
            arches__overlap=PackageRepository.PORTS_ARCHES,
            enabled=True,
            default=True,
        ).first()

    def delete(self):
        main_archive = self.get_main_archive()
        ports_archive = self.get_ports_archive()
        if self in (main_archive, ports_archive):
            raise ValidationError("Cannot delete default Ubuntu archives.")
        super().delete()
