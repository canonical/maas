# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to boot source changes."""

__all__ = [
    "signals",
]

from django.db.models.signals import post_save
from maasserver.bootsources import cache_boot_sources
from maasserver.models.bootsource import BootSource
from maasserver.utils.orm import post_commit_do
from maasserver.utils.signals import SignalsManager
from twisted.internet import reactor


signals = SignalsManager()


def update_boot_source_cache(sender, instance, **kwargs):
    """Update the `BootSourceCache` using the updated source.

    This only begins after a successful commit to the database, and is then
    run in a thread. Nothing waits for its completion.
    """
    post_commit_do(reactor.callLater, 0, cache_boot_sources)


signals.watch(post_save, update_boot_source_cache, BootSource)


# Enable all signals by default.
signals.enable()
