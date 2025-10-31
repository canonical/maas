# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS update and reload service for the region controller."""

from datetime import timedelta
import re

from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks

from maasserver.dns.config import current_zone_serial, dns_update_all_zones
from maasserver.models import Config
from maasserver.utils.threads import deferToDatabase
from provisioningserver.dns.config import get_zone_file_config_dir
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import synchronous

log = LegacyLogger()

ZONE_SERIAL_REGEX = re.compile(r"\s*([0-9]+)\s*\;\s*serial")


class DNSReloadService(TimerService):
    """
    This service aims to update and reload bind on this specific controller every minute.
    """

    interval = timedelta(seconds=60).total_seconds()

    def __init__(self, reactor):
        super().__init__(self.interval, self._tryUpdate)
        self.clock = reactor
        self.update_running = False

    @inlineCallbacks
    def _tryUpdate(self):
        """Update the BIND server running on this host."""
        if self.update_running:
            log.info("DNS update/reload still running.")
            return

        self.update_running = True
        try:
            yield deferToDatabase(self._run)
        except Exception as e:
            log.warn(f"Failed to update and reload DNS: {e}")
        finally:
            self.update_running = False

    @synchronous
    def _run(self) -> str | None:
        """
        Returns the current serial if found, None otherwise.
        """
        internal_domain = Config.objects.get_config("maas_internal_domain")

        # any zonefile will have the same serial
        local_serial = None
        try:
            file_path = get_zone_file_config_dir() / f"zone.{internal_domain}"
            with open(file_path, "r") as f:
                for line in f.readlines():
                    result = ZONE_SERIAL_REGEX.findall(line)
                    if result:
                        local_serial = result[0]
        except Exception as e:
            log.warn(
                f"Failed to retrieve local serial. Will try to full reload. {e}"
            )

        # If we fail to find the local serial, always reload.
        if local_serial is None:
            return dns_update_all_zones(requires_reload=True)
        else:
            # If the local serial is behind the one in the db, reload.
            current_serial = current_zone_serial()
            if int(local_serial) < int(current_serial):
                return dns_update_all_zones(
                    requires_reload=True, serial=current_serial
                )
            else:
                log.info(
                    "BIND is already up to date. Skipping update and reload."
                )
        # We are already up to date. Nothing to do.
        return None
