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
from textwrap import dedent

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

# Built-in script to run lshw.
LSHW_SCRIPT = dedent("""\
    #!/bin/sh
    lshw -xml
    """)

# Built-in commissioning scripts.  These go into the commissioning
# tarball together with user-provided commissioning scripts.
# To keep namespaces separated, names of the built-in scripts must be
# prefixed with "00-maas-" or "99-maas-".
BUILTIN_COMMISSIONING_SCRIPTS = {
    '00-maas-01-lshw': LSHW_SCRIPT.encode('ascii'),
}


def add_script_to_archive(tarball, name, content):
    """Add a commissioning script to an archive of commissioning scripts."""
    assert isinstance(content, bytes), "Script content must be binary."
    tarinfo = tarfile.TarInfo(name=os.path.join(ARCHIVE_PREFIX, name))
    tarinfo.size = len(content)
    tarinfo.mode = 0755  # u=rwx,go=rx
    tarball.addfile(tarinfo, BytesIO(content))


class CommissioningScriptManager(Manager):
    """Utility for the collection of `CommissioningScript`s."""

    def get_archive(self):
        """Produce a tar archive of all commissioning scripts.

        Each of the scripts will be in the `ARCHIVE_PREFIX` directory.
        """
        binary = BytesIO()
        tarball = tarfile.open(mode='w', fileobj=binary)
        scripts = sorted(
            BUILTIN_COMMISSIONING_SCRIPTS.items() +
            [(script.name, script.content) for script in self.all()])
        for name, content in scripts:
            add_script_to_archive(tarball, name, content)
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
