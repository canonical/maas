# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to boot source changes."""

__all__ = [
    "signals",
]

from django.db.models.signals import (
    post_delete,
    post_init,
    post_save,
)
from maasserver.bootsources import cache_boot_sources
from maasserver.models.bootsource import BootSource
from maasserver.utils.orm import post_commit_do
from maasserver.utils.signals import SignalsManager
from twisted.internet import reactor


signals = SignalsManager()


def is_first_run(sender, instance, *args, **kwargs):
    """Store whether or not this is the first BootSource added to MAAS.

    On first run the ImportResourceService sets the default BootSource then
    caches the stream's contents as normal. Setting the default BootSource
    triggers this signal. This prevents updating the cache twice.
    """
    instance.__is_first_run = BootSource.objects.count() == 0


def update_boot_source_cache(sender, instance, *args, **kwargs):
    """Update the `BootSourceCache` using the updated source.

    This only begins after a successful commit to the database, and is then
    run in a thread. Nothing waits for its completion.
    """
    if not isinstance(instance, BootSource) or not instance.__is_first_run:
        post_commit_do(reactor.callLater, 0, cache_boot_sources)


signals.watch(post_init, is_first_run, BootSource)
signals.watch(post_save, update_boot_source_cache, BootSource)
signals.watch(post_delete, update_boot_source_cache, BootSource)
signals.watch_config(update_boot_source_cache, "enable_http_proxy")
signals.watch_config(update_boot_source_cache, "http_proxy")


# Enable all signals by default.
signals.enable()
