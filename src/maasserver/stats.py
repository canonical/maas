# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resources."""

__all__ = [
    "StatsService",
    "STATS_SERVICE_PERIOD",
]

from datetime import timedelta

from maasserver.models import Config
from maasserver.utils.orm import transactional
from maasserver.utils.stats import make_maas_user_agent_request
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from twisted.application.internet import TimerService


log = LegacyLogger()

# How often the import service runs.
STATS_SERVICE_PERIOD = timedelta(hours=24)


class StatsService(TimerService, object):
    """Service to periodically get stats.

    This will run immediately when it's started, then once again every
    24 hours, though the interval can be overridden by passing it to
    the constructor.
    """

    def __init__(self, interval=STATS_SERVICE_PERIOD):
        super(StatsService, self).__init__(
            interval.total_seconds(), self.maybe_make_stats_request)

    def maybe_make_stats_request(self):
        def determine_stats_request():
            if Config.objects.get_config('enable_analytics'):
                make_maas_user_agent_request()

        d = deferToDatabase(transactional(determine_stats_request))
        d.addErrback(log.err, "Failure performing user agent request.")
        return d
