# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Nonces cleanup utilities."""

import time

from piston3.models import Nonce
from piston3.oauth import OAuthServer
from twisted.application.internet import TimerService

from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.utils.twisted import synchronous

timestamp_threshold = OAuthServer.timestamp_threshold


def cleanup_old_nonces():
    """Clean up old nonces.

    This method does two things:
    - it creates a "checkpoint" nonce which stores its creation
      time.
    - it removes the expired nonces by using existing "checkpoint"
      nonces to figure out which nonces can be safely deleted.

    Given the two-step nature of this method, it needs to be called
    at least twice, the two calls being separated by 5 minutes, to
    actually be able to delete old nonces.
    The typical usage is to call this at regular intervals in a
    cron-like fashion.
    """
    create_checkpoint_nonce()
    # Delete old nonces.
    checkpoint = find_checkpoint_nonce()
    if checkpoint is None:
        return 0
    return delete_old_nonces(checkpoint)


def create_checkpoint_nonce():
    """Create a "checkpoint" nonce.

    A "checkpoint" nonce is a Nonce with empty strings in
    'token_key' and 'consumer_key' and its creation time in the
    'key' field.
    """
    now = time.time()
    Nonce.objects.get_or_create(
        token_key="", consumer_key="", key=get_time_string(now)
    )


# Key prefix used when creating checkpoint nonces to avoid clashing with
# real-world nonce created by piston.
key_prefix = "CHECKPOINT#"


def get_time_string(time_value):
    """Convert a time value, as returned by time.time() into a string."""
    return f"{key_prefix}{time_value:f}"


def delete_old_nonces(checkpoint):
    """Delete nonces older than the given nonce."""
    nonce_to_delete = Nonce.objects.filter(id__lte=checkpoint.id)
    count = nonce_to_delete.count()
    nonce_to_delete.delete()
    return count


def find_checkpoint_nonce():
    """Return the most recent "checkpoint" nonce.

    The returned nonce will be older than 'timestamp_threshold'.
    Returns None if such a nonce does not exist.
    """
    time_limit = get_time_string(time.time() - timestamp_threshold)
    nonces = Nonce.objects.filter(
        token_key="",
        consumer_key="",
        key__lte=time_limit,
        key__startswith=key_prefix,
    )
    try:
        return nonces.latest("id")
    except Nonce.DoesNotExist:
        return None


class NonceCleanupService(TimerService):
    """Service to periodically clean-up old nonces.

    This will run immediately when it's started, then once again each
    day, though the interval can be overridden by passing it to the
    constructor.
    """

    def __init__(self, interval=(24 * 60 * 60)):
        cleanup = synchronous(transactional(cleanup_old_nonces))
        super().__init__(interval, deferToDatabase, cleanup)
