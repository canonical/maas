# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to boot resource file changes."""


from django.db.models.signals import post_delete

from maasserver.models.bootresourcefile import BootResourceFile
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def delete_large_file(sender, instance, **kwargs):
    """Call delete on the LargeFile, now that the relation has been removed.
    If this was the only resource file referencing this LargeFile then it will
    be delete.

    This is done using the `post_delete` signal because only then has the
    relation been removed.
    """
    if (largefile := instance.largefile) is not None:
        largefile.delete()


signals.watch(post_delete, delete_large_file, BootResourceFile)


# Enable all signals by default.
signals.enable()
