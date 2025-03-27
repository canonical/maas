# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to boot source changes."""

from django.db.models.signals import post_delete, post_save

from maasserver.bootsources import update_boot_source_cache
from maasserver.models.bootsource import BootSource
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def save_boot_source_cache(sender, instance, *args, **kwargs):
    """On first run the ImportResourceService sets the default BootSource then
    caches the stream's contents as normal. Setting the default BootSource
    triggers this signal. This prevents updating the cache twice.
    """
    # Don't run if the first row and newly created.
    if instance.id != 1 and BootSource.objects.exists():
        update_boot_source_cache()


def delete_boot_source(sender, instance, *args, **kwargs):
    """Wrap update_boot_source_cache and ignore the signal arguments"""
    update_boot_source_cache()


signals.watch(post_save, save_boot_source_cache, BootSource)
signals.watch(post_delete, delete_boot_source, BootSource)


# Enable all signals by default.
signals.enable()
