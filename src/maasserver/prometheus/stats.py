# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Prometheus integration"""

__all__ = [
    "PrometheusService",
    "PROMETHEUS_SERVICE_PERIOD",
]

from datetime import timedelta
import json

from django.http import (
    HttpResponse,
    HttpResponseNotFound,
)
from maasserver.models import Config
from maasserver.prometheus import (
    prom_cli,
    PROMETHEUS_SUPPORTED,
)
from maasserver.prometheus.utils import (
    create_metrics,
    MetricDefinition,
    PrometheusMetrics,
)
from maasserver.stats import (
    get_kvm_pods_stats,
    get_maas_stats,
    get_machines_by_architecture,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from twisted.application.internet import TimerService


log = LegacyLogger()

STATS_DEFINITIONS = [
    MetricDefinition(
        'Gauge', 'machine_status', 'Number of machines per status',
        ['status']),
    MetricDefinition(
        'Gauge', 'nodes',
        'Number of nodes per type (e.g. racks, machines, etc)',
        ['type']),
    MetricDefinition(
        'Gauge', 'networks', 'General statistics for subnets',
        ['type']),
    MetricDefinition(
        'Gauge', 'machine_resources',
        'Amount of combined resources for all machines',
        ['resource']),
    MetricDefinition(
        'Gauge', 'kvm_pods', 'General stats for KVM pods',
        ['type']),
    MetricDefinition(
        'Gauge', 'machine_arches', 'Number of machines per architecture',
        ['arches'])
]


def prometheus_stats_handler(request):
    if not Config.objects.get_config('prometheus_enabled'):
        return HttpResponseNotFound()

    metrics = create_metrics(STATS_DEFINITIONS)
    update_prometheus_stats(metrics)
    return HttpResponse(
        content=metrics.generate_latest(), content_type="text/plain")


def update_prometheus_stats(metrics: PrometheusMetrics):
    """Update metrics in a PrometheusMetrics based on database values."""
    stats = json.loads(get_maas_stats())
    architectures = get_machines_by_architecture()
    pods = get_kvm_pods_stats()

    # Gather counter for machines per status
    for status, machines in stats['machine_status'].items():
        metrics.update(
            'machine_status', 'set', value=machines, labels={'status': status})

    # Gather counter for number of nodes (controllers/machine/devices)
    for ctype, number in stats['controllers'].items():
        metrics.update(
            'nodes', 'set', value=number, labels={'type': ctype})
    for ctype, number in stats['nodes'].items():
        metrics.update(
            'nodes', 'set', value=number, labels={'type': ctype})

    # Gather counter for networks
    for stype, number in stats['network_stats'].items():
        metrics.update(
            'networks', 'set', value=number, labels={'type': stype})

    # Gather overall amount of machine resources
    for resource, value in stats['machine_stats'].items():
        metrics.update(
            'machine_resources', 'set', value=value,
            labels={'resource': resource})

    # Gather all stats for pods
    for resource, value in pods.items():
        if isinstance(value, dict):
            for r, v in value.items():
                metrics.update(
                    'kvm_pods', 'set', value=v,
                    labels={'type': '{}_{}'.format(resource, r)})
        else:
            metrics.update(
                'kvm_pods', 'set', value=value,
                labels={'type': resource})

    # Gather statistics for architectures
    if len(architectures.keys()) > 0:
        for arch, machines in architectures.items():
            metrics.update(
                'machine_arches', 'set', value=machines,
                labels={'arches': arch})

    return metrics


def push_stats_to_prometheus(maas_name, push_gateway):
    metrics = create_metrics(STATS_DEFINITIONS)
    update_prometheus_stats(metrics)
    prom_cli.push_to_gateway(
        push_gateway, job='stats_for_%s' % maas_name,
        registry=metrics.registry)


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
            if (not PROMETHEUS_SUPPORTED or not config['prometheus_enabled'] or
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
