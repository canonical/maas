from pathlib import Path
import re

from provisioningserver.prometheus.utils import (
    MetricDefinition,
    PrometheusMetrics,
)

MEMINFO_FIELDS = [
    "AnonPages",
    "Buffers",
    "Cached",
    "CommitLimit",
    "Committed_AS",
    "Dirty",
    "HugePages_Free",
    "HugePages_Rsvd",
    "HugePages_Surp",
    "HugePages_Total",
    "Mapped",
    "MemAvailable",
    "MemFree",
    "MemTotal",
    "PageTables",
    "Shmem",
    "Slab",
    "SReclaimable",
    "SUnreclaim",
    "SwapCached",
    "SwapFree",
    "SwapTotal",
    "VmallocChunk",
    "VmallocTotal",
    "VmallocUsed",
    "Writeback",
    "WritebackTmp",
]

# Fields for the "cpu" row in /proc/stat, in the order they appear in
CPU_TIME_FIELDS = [
    "user",
    "nice",
    "system",
    "idle",
    "iowait",
    "irq",
    "softirq",
    "steal",
    "guest",
    "guest_nice",
]


# CPU counters are based on the system clock multiplier. This it technically
# dynamic and can be retrieved via sysconf(), but it's currently 100 on most
# platforms and recent kernels.
#
# Prometheus libraries also hardcodes it the same way (see
# https://github.com/prometheus/procfs)
USER_HZ = 100


def node_metrics_definitions():
    """Return a list of MetricDefinitions for memory and cpu metrics."""
    definitions = [
        MetricDefinition(
            "Gauge",
            f"maas_node_mem_{field}",
            f"Memory information field {field}",
            labels=["service_type"],
        )
        for field in MEMINFO_FIELDS
    ]
    definitions.append(
        MetricDefinition(
            "Counter",
            "maas_node_cpu_time",
            "CPU time",
            labels=["service_type", "state"],
        )
    )
    return definitions


def update_memory_metrics(prometheus_metrics: PrometheusMetrics, path=None):
    """Update memory-related metrics."""
    from provisioningserver.prometheus.metrics import GLOBAL_LABELS

    metric_values = _collect_memory_values(path=path)
    for field in MEMINFO_FIELDS:
        value = metric_values.get(field)
        if value is not None:
            prometheus_metrics.update(
                f"maas_node_mem_{field}",
                "set",
                value=value,
                labels={"service_type": GLOBAL_LABELS["service_type"]},
            )


def update_cpu_metrics(prometheus_metrics: PrometheusMetrics, path=None):
    """Update memory-related metrics."""
    from provisioningserver.prometheus.metrics import GLOBAL_LABELS

    cpu_values = _collect_cpu_values(path=path)
    for field in CPU_TIME_FIELDS:
        value = cpu_values.get(field)
        if value is not None:
            prometheus_metrics.update(
                "maas_node_cpu_time",
                "set",
                value=value / USER_HZ,
                labels={
                    "service_type": GLOBAL_LABELS["service_type"],
                    "state": field,
                },
            )


def _collect_memory_values(path=None):
    """Read /proc/meminfo and return values."""
    if not path:
        path = Path("/proc/meminfo")
    split_re = re.compile(r"\s+")
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
        path = Path("/proc/stat")
    # The first line contains global cpu counters
    cpu_line = path.read_text().splitlines()[0]
    split_re = re.compile(r"\s+")
    # skip the first "cpu" field
    tokens = split_re.split(cpu_line)[1:]
    return dict(zip(CPU_TIME_FIELDS, (int(token) for token in tokens)))
