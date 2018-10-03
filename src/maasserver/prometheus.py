# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Prometheus integration"""

__all__ = [
    "PrometheusService",
    "PROMETHEUS_SERVICE_PERIOD",
]

from datetime import timedelta
import json

from maasserver.models import Config
from maasserver.stats import get_maas_stats
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from twisted.application.internet import TimerService


try:
    from prometheus_client import (
        CollectorRegistry,
        Gauge,
        push_to_gateway,
    )
    PROMETHEUS = True
except:
    PROMETHEUS = False

log = LegacyLogger()


def push_stats_to_prometheus(maas_name, push_gateway):
    registry = CollectorRegistry()
    stats = json.loads(get_maas_stats())

    # Gather counter for machines per status
    counter = Gauge(
        "machine_status", "Number per machines per stats",
        ["status"], registry=registry)
    for status, machines in stats['machine_status'].items():
        counter.labels(status).set(machines)

    push_to_gateway(
        push_gateway, job='stats_for_%s' % maas_name, registry=registry)


# Define the default time the service interval is run.
# This can be overriden by the config option.
PROMETHEUS_SERVICE_PERIOD = timedelta(minutes=60)


class PrometheusService(TimerService, object):
    """Service to periodically push stats to Prometheus

    This will run immediately when it's started, by default, it will run
    every 60 minutes, though the interval can be overridden (see
    prometheus_push_internval global config).
    """

    def __init__(self, interval=PROMETHEUS_SERVICE_PERIOD):
        super(PrometheusService, self).__init__(
            interval.total_seconds(), self.maybe_push_prometheus_stats)

    def maybe_push_prometheus_stats(self):
        def determine_stats_request():
            config = Config.objects.get_configs([
                'maas_name', 'prometheus_enabled', 'prometheus_push_gateway',
                'prometheus_push_interval'])
            # Update interval
            self._update_interval(
                timedelta(minutes=config['prometheus_push_interval']))
            # Determine if we can run the actual update.
            if (not PROMETHEUS or not config['prometheus_enabled'] or
                    config['prometheus_push_gateway'] is None):
                return
            # Run updates.
            push_stats_to_prometheus(
                config['maas_name'], config['prometheus_push_gateway'])

        d = deferToDatabase(transactional(determine_stats_request))
        d.addErrback(
            log.err,
            "Failure pushing stats to prometheus gateway")
        return d

    def _update_interval(self, interval):
        """Change the update interval."""
        interval_seconds = interval.total_seconds()
        if self.step == interval_seconds:
            return
        self._loop.interval = self.step = interval_seconds
        if self._loop.running:
            self._loop.reset()
