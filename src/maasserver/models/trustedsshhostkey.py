# Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from django.db import models

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class TrustedSshHostKey(CleanSave, TimestampedModel):
    """A trusted SSH host key for a remote host.

    Stores known public keys for hosts (e.g. BMCs, rack controllers)
    so that SSH connections can verify the host's identity.
    """

    host = models.CharField(max_length=255)
    key_type = models.CharField(
        max_length=64
    )  # e.g. ssh-rsa, ecdsa-sha2-nistp256
    public_key = models.TextField()
    label = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "maasserver_trustedsshhostkey"
        unique_together = ("host", "key_type", "public_key")
        verbose_name = "Trusted SSH Host Key"
        verbose_name_plural = "Trusted SSH Host Keys"
