# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for observed reverse-DNS entries."""

from typing import List

from django.contrib.postgres.fields import ArrayField
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    GenericIPAddressField,
    Manager,
    TextField,
)

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.logger import LegacyLogger

log = LegacyLogger()


class RDNSManager(Manager):
    """Manager for reverse-DNS entries.."""

    def get_current_entry(self, ip: str, observer):
        """Returns the current reverse DNS entry for the specified IP.

        :param ip: The IP address whose entry to retrieve.
        :param observer: The RegionController that made the observation.
        """
        return self.filter(ip=ip, observer=observer).first()

    def delete_current_entry(self, ip: str, observer):
        """Deletes the current reverse DNS entry for the specified `ip`.

        If no entry exists, this call is a no-op.

        :param ip: The IP address whose PTR records were looked up.
        :param observer: The RegionController that made the observation.
        """
        entry = self.get_current_entry(ip, observer)
        if entry is not None:
            log.debug(
                "Deleted reverse DNS entry: '{ip}' (resolved to {res}).",
                ip=entry.ip,
                res=", ".join("%r" % hostname for hostname in entry.hostnames),
            )
            entry.delete()

    def set_current_entry(self, ip: str, results: List[str], observer):
        """Sets the current reverse DNS entry for the specified `ip`.

        :param ip: The IP address whose PTR records were looked up.
        :param results: The list of reverse hostnames for the given `ip`.
        :param observer: The RegionController that made the observation.
        """
        assert len(results) > 0, "Results must be non-empty to set RDNS entry."
        # By convention, the first item in the list is considered the "best".
        preferred_hostname = results[0]
        entry = self.get_current_entry(ip, observer)
        if entry is None:
            # No mapping exists for this reverse-DNS entry yet, so create one
            # and then log it.
            rdns = RDNS(
                ip=ip,
                hostname=preferred_hostname,
                hostnames=results,
                observer=observer,
            )
            rdns.save()
            log.debug(
                "New reverse DNS entry: '{ip}' resolves to {res}.",
                ip=ip,
                res=", ".join("%r" % result for result in results),
            )
        else:
            # Always update the 'updated' date, so we know when the last time
            # we saw this hostname was.
            updated = ["updated"]
            # Update existing entry, being careful to note the fields that
            # have changed.
            if entry.hostname != preferred_hostname:
                entry.hostname = preferred_hostname
                updated.append("hostname")
            if entry.hostnames != results:
                entry.hostnames = results
                updated.append("hostnames")
            # If something significant changed, log it.
            if len(updated) > 1:
                log.debug(
                    "Reverse DNS entry updated: '{ip}' resolves to {res}.",
                    ip=ip,
                    res=", ".join("%r" % result for result in results),
                )
            entry.save(update_fields=updated)


class RDNS(CleanSave, TimestampedModel):
    """Represents data gathered from reverse DNS for a particular IP address.

    :ivar ip: Observed IP address.
    :ivar hostname: Most recent reverse DNS entry.
    """

    class Meta:
        verbose_name = "Reverse-DNS entry"
        verbose_name_plural = "Reverse-DNS entries"
        unique_together = ("ip", "observer")

    objects = RDNSManager()

    # IP address for the reverse-DNS entry.
    ip = GenericIPAddressField(
        unique=False,
        null=False,
        editable=False,
        blank=False,
        verbose_name="IP",
    )

    # "Primary" reverse-DNS hostname. (Since reverse DNS lookups can return
    # more than one entry, we'll need to make an educated guess as to which
    # is the "primary".) This will be coalesced with the other data in the
    # discovery view to present the default hostname for the IP.
    hostname = CharField(max_length=256, null=True)

    # List of all hostnames returned by the lookup. (Useful for
    # support/debugging, in case we guess incorrectly about the "primary"
    # hostname -- and in case we ever want to show them all.)
    hostnames = ArrayField(TextField(), default=list)

    # Region controller that observed the hostname.
    observer = ForeignKey(
        "Node",
        unique=False,
        blank=False,
        null=False,
        editable=False,
        on_delete=CASCADE,
    )
