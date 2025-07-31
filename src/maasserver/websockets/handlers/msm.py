# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS Site Manager handler for the WebSocket connection."""

from dataclasses import asdict

from maascommon.enums.msm import MSMStatusEnum
from maasserver.sqlalchemy import service_layer
from maasserver.websockets.base import Handler


class MAASSiteManagerHandler(Handler):
    class Meta:
        allowed_methods = ["status"]
        handler_name = "msm"

    def status(self, params):
        """Get the status of enrolment"""
        status = service_layer.services.msm.get_status()
        if not status:
            return {
                "sm_url": None,
                "start_time": None,
                "running": MSMStatusEnum.NOT_CONNECTED,
            }
        return asdict(status)
