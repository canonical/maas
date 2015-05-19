# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service class for the monitored tgt service."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "TGTService",
    ]

from provisioningserver.drivers.service import (
    Service,
    SERVICE_STATE,
)


class TGTService(Service):
    """Monitored tgt service."""

    name = "tgt"
    service_name = "tgt"

    def get_expected_state(self):
        """Return a the expected state for the tgt service.

        The tgt service should always be on. No condition exists where it
        should be off.
        """
        return SERVICE_STATE.ON
