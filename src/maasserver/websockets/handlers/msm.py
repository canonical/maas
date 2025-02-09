# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS Site Manager handler for the WebSocket connection."""

from maasserver.enum import MSM_STATUS
from maasserver.msm import msm_status
from maasserver.websockets.base import Handler


class MAASSiteManagerHandler(Handler):
    class Meta:
        allowed_methods = ["status"]
        handler_name = "msm"

    def status(self, params):
        """Get the status of enrolment"""
        status = msm_status()
        if not status:
            return {
                "sm-url": None,
                "start-time": None,
                "running": MSM_STATUS.NOT_CONNECTED,
            }
        return status
