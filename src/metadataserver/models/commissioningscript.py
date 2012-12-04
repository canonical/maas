# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom commissioning scripts, and their database backing."""


from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'CommissioningScript',
    ]

from io import BytesIO
import os.path
import tarfile

from django.db.models import (
    CharField,
    Manager,
    Model,
    )
from metadataserver import DefaultMeta
from metadataserver.fields import BinaryField

# Path prefix for commissioning scripts.  Commissioning scripts will be
# extracted into this directory.
ARCHIVE_PREFIX = "commissioning.d"


class CommissioningScriptManager(Manager):
    """Utility for the collection of `CommissioningScript`s."""

    def get_archive(self):
        """Produce a tar archive of all commissioning scripts.

        Each of the scripts will be in the `ARCHIVE_PREFIX` directory.
        """
        binary = BytesIO()
        tarball = tarfile.open(mode='w', fileobj=binary)
        for script in self.all().order_by('name'):
            path = os.path.join(ARCHIVE_PREFIX, script.name)
            tarinfo = tarfile.TarInfo(name=path)
            tarinfo.size = len(script.content)
            tarball.addfile(tarinfo, BytesIO(script.content))
        tarball.close()
        binary.seek(0)
        return binary.read()


class CommissioningScript(Model):
    """User-provided commissioning script.

    Actually a commissioning "script" could be a binary, e.g. because a
    hardware vendor supplied an update in the form of a binary executable.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = CommissioningScriptManager()

    name = CharField(max_length=255, null=False, editable=True, unique=True)
    content = BinaryField(null=False)
