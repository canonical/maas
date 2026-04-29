# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to boot source changes."""

from django.db.models.signals import post_save

from maasserver.bootsources import update_boot_source_cache
from maasserver.models.bootsource import BootSource
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def save_boot_source_cache(sender, instance, *args, **kwargs):
    update_boot_source_cache(instance.id)


signals.watch(post_save, save_boot_source_cache, BootSource)

# Enable all signals by default.
signals.enable()
