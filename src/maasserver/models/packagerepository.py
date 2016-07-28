# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""PackageRepository objects."""

__all__ = [
    "PackageRepository",
    ]

from django.contrib.postgres.fields import ArrayField
from django.db.models import (
    BooleanField,
    CharField,
    Manager,
    TextField,
    URLField,
)
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class PackageRepositoryManager(Manager):
    """Manager for `PackageRepository` class."""


class PackageRepository(CleanSave, TimestampedModel):
    """A `PackageRepository`."""

    MAIN_ARCHES = ['amd64', 'i386']
    PORTS_ARCHES = ['armhf', 'arm64', 'powerpc', 'ppc64el']

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = PackageRepositoryManager()

    name = CharField(max_length=41, unique=True, default='')

    description = TextField(blank=True, default='')

    url = URLField(blank=False, help_text="The URL of the PackageRepository.")

    distro = CharField(max_length=41, default='ubuntu', editable=False)

    pockets = ArrayField(TextField(), blank=True, null=True, default=list)

    components = ArrayField(TextField(), blank=True, null=True, default=list)

    arches = ArrayField(TextField(), blank=True, null=True, default=list)

    key = TextField(default='', editable=False)

    default = BooleanField(default=False)

    enabled = BooleanField(default=True)

    def __str__(self):
        return "%s (%s)" % (self.id, self.name)

    @classmethod
    def get_main_archive(cls):
        repo = cls.objects.filter(
            arches__overlap=PackageRepository.MAIN_ARCHES,
            distro='ubuntu',
            enabled=True,
            default=True).first()
        if repo is None:
            return "http://archive.ubuntu.com/ubuntu"
        else:
            return repo.url

    @classmethod
    def get_ports_archive(cls):
        repo = cls.objects.filter(
            arches__overlap=PackageRepository.PORTS_ARCHES,
            distro='ubuntu',
            enabled=True,
            default=True).first()
        if repo is None:
            return "http://ports.ubuntu.com/ubuntu-ports"
        else:
            return repo.url
