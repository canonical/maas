# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Delete KeySource when no more keys are present."""


from django.db.models.signals import post_delete

from maasserver.models import KeySource, SSHKey
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def post_delete_keysource_when_no_more_keys(sender, instance, **kwargs):
    """Delete Keysource when no more keys."""
    keysource = None
    try:
        keysource = instance.keysource
    except KeySource.DoesNotExist:
        pass  # Nothing to do.
    else:
        if keysource is not None:
            if not keysource.sshkey_set.exists():
                keysource.delete()


signals.watch(
    post_delete, post_delete_keysource_when_no_more_keys, sender=SSHKey
)


# Enable all signals by default.
signals.enable()
