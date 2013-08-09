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
    'BUILTIN_COMMISSIONING_SCRIPTS',
    'CommissioningScript',
    ]

from io import BytesIO
import os.path
import tarfile
from textwrap import dedent
import time

from django.db.models import (
    CharField,
    Manager,
    Model,
    )
from maasserver.models.tag import Tag
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


def set_hardware_details(node, raw_content):
    """Process the results of LSHW_SCRIPT."""
    node.set_hardware_details(raw_content)


# Built-in script to detect virtual instances. It will only detect QEMU
# for now and may need expanding/generalising at some point.
VIRTUALITY_SCRIPT = dedent("""\
    #!/bin/sh
    grep '^model name.*QEMU.*' /proc/cpuinfo >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "virtual"
    else
        echo "notvirtual"
    fi
    """)


def set_virtual_tag(node, raw_content):
    """Process the results of VIRTUALITY_SCRIPT."""
    tag, _ = Tag.objects.get_or_create(name='virtual')
    if 'notvirtual' in raw_content:
        node.tags.remove(tag)
    else:
        node.tags.add(tag)

# Built-in commissioning scripts.  These go into the commissioning
# tarball together with user-provided commissioning scripts.
# To keep namespaces separated, names of the built-in scripts must be
# prefixed with "00-maas-" or "99-maas-".
#
# The dictionary is keyed on the output filename that the script
# produces. This is so it can be looked up later in the post-processing
# hook.
#
# The contents of each dictionary entry are another dictionary with
# keys:
#   "name" -> the script's name
#   "content" -> the actual script
#   "hook" -> a post-processing hook.
#
# The post-processing hook is a function that will be passed the node
# and the raw content of the script's output, e.g. "hook(node, raw_content)"
BUILTIN_COMMISSIONING_SCRIPTS = {
    '00-maas-01-lshw.out': {
        'name': '00-maas-01-lshw',
        'content': LSHW_SCRIPT.encode('ascii'),
        'hook': set_hardware_details,
    },
    '00-maas-02-virtuality.out': {
        'name': '00-maas-02-virtuality',
        'content': VIRTUALITY_SCRIPT.encode('ascii'),
        'hook': set_virtual_tag,
    },
}


def add_script_to_archive(tarball, name, content, mtime):
    """Add a commissioning script to an archive of commissioning scripts."""
    assert isinstance(content, bytes), "Script content must be binary."
    tarinfo = tarfile.TarInfo(name=os.path.join(ARCHIVE_PREFIX, name))
    tarinfo.size = len(content)
    # Mode 0755 means: u=rwx,go=rx
    tarinfo.mode = 0755
    # Modification time defaults to Epoch, which elicits annoying
    # warnings when decompressing.
    tarinfo.mtime = mtime
    tarball.addfile(tarinfo, BytesIO(content))


class CommissioningScriptManager(Manager):
    """Utility for the collection of `CommissioningScript`s."""

    def get_archive(self):
        """Produce a tar archive of all commissioning scripts.

        Each of the scripts will be in the `ARCHIVE_PREFIX` directory.
        """
        mtime = time.time()
        binary = BytesIO()
        tarball = tarfile.open(mode='w', fileobj=binary)
        scripts = sorted(
            [(script['name'], script['content']) for script
                in BUILTIN_COMMISSIONING_SCRIPTS.itervalues()] +
            [(script.name, script.content) for script in self.all()])
        for name, content in scripts:
            add_script_to_archive(
                tarball=tarball, name=name, content=content, mtime=mtime)
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
