from pathlib import Path
import re

from provisioningserver.prometheus.utils import (
    MetricDefinition,
    PrometheusMetrics,
)


MEMINFO_FIELDS = [
    'AnonPages',
    'Buffers',
    'Cached',
    'CommitLimit',
    'Committed_AS',
    'Dirty',
    'HugePages_Free',
    'HugePages_Rsvd',
    'HugePages_Surp',
    'HugePages_Total',
    'Mapped',
    'MemAvailable',
    'MemFree',
    'MemTotal',
    'PageTables',
    'Shmem',
    'Slab',
    'SReclaimable',
    'SUnreclaim',
    'SwapCached',
    'SwapTotal',
    'SwapFree',
    'VmallocChunk'
    'VmallocTotal',
    'VmallocUsed',
    'Writeback',
    'WritebackTmp',
]

CPU_TIME_FIELDS = [
    'user', 'nice', 'system', 'idle', 'iowait', 'irq', 'softirq', 'steal',
    'guest', 'guest_nice',
]


def node_metrics_definitions():
    """Return a list of MetricDefinitions for memory and cpu metrics."""
    mem_defs = [
        MetricDefinition(
            'Gauge', 'maas_node_mem_{}'.format(field),
            'Memory information field {}'.format(field), [])
        for field in MEMINFO_FIELDS]
    cpu_defs = [
        MetricDefinition(
            'Gauge', 'maas_node_cpu_time_{}'.format(field),
            'CPU "{}" time'.format(field), [])
        for field in CPU_TIME_FIELDS]
    return mem_defs + cpu_defs


def update_memory_metrics(prometheus_metrics: PrometheusMetrics, path=None):
    """Update memory-related metrics."""
    metric_values = _collect_memory_values(path=path)
    for field in MEMINFO_FIELDS:
        value = metric_values.get(field)
        if value is not None:
            prometheus_metrics.update(
                'maas_node_mem_{}'.format(field), 'set', value=value)


def update_cpu_metrics(prometheus_metrics: PrometheusMetrics, path=None):
    """Update memory-related metrics."""
    cpu_values = _collect_cpu_values(path=path)
    for field in CPU_TIME_FIELDS:
        value = cpu_values.get(field)
        if value is not None:
            prometheus_metrics.update(
                'maas_node_cpu_time_{}'.format(field), 'set', value=value)


def _collect_memory_values(path=None):
    """Read /proc/meminfo and return values."""
    if not path:
        path = Path('/proc/meminfo')
    split_re = re.compile(r'\s+')
    metrics = {}
    for line in path.read_text().splitlines():
        # some metrics have a a size suffix, which is always "kB"
        key, value, *_ = split_re.split(line)
        key = key[:-1]  # skip the trailing ':'
        if key in MEMINFO_FIELDS:
            metrics[key] = int(value)
    return metrics


def _collect_cpu_values(path=None):
    """Read /proc/stat and return CPU values."""
    if not path:
        path = Path('/proc/stat')
    # The first line contains global cpu counters
    cpu_line = path.read_text().splitlines()[0]
    split_re = re.compile(r'\s+')
    # skip the first "cpu" field
    tokens = split_re.split(cpu_line)[1:]
    return dict(
        zip(CPU_TIME_FIELDS, (int(token) for token in tokens)))
