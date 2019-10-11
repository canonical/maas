from pathlib import Path
from textwrap import dedent

from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase
import prometheus_client
from provisioningserver.prometheus import metrics
from provisioningserver.prometheus.collectors import (
    MEMINFO_FIELDS,
    node_metrics_definitions,
    update_cpu_metrics,
    update_memory_metrics,
)
from provisioningserver.prometheus.utils import create_metrics


class TestNodeMetricsDefinitions(MAASTestCase):
    def test_definitions(self):
        definitions = node_metrics_definitions()
        # only one metric for memory
        metrics_count = len(MEMINFO_FIELDS) + 1
        self.assertEqual(len(definitions), metrics_count)
        for definition in definitions:
            if definition.name.startswith("maas_node_mem"):
                self.assertEqual("Gauge", definition.type)
            else:
                self.assertEqual("Counter", definition.type)


class TestUpdateMemoryMetrics(MAASTestCase):
    def test_update_metrics(self):
        self.patch(metrics, "GLOBAL_LABELS", {"service_type": "rack"})
        tempdir = self.useFixture(TempDirectory())
        meminfo = Path(tempdir.path) / "meminfo"
        meminfo.write_text(
            dedent(
                """\
            MemTotal:         123 Kb
            SwapCached:       456 Kb
            VmallocUsed:      789 Kb
            HugePages_Total:  321
            """
            )
        )
        prometheus_metrics = create_metrics(
            node_metrics_definitions(),
            registry=prometheus_client.CollectorRegistry(),
        )
        update_memory_metrics(prometheus_metrics, path=meminfo)
        output = prometheus_metrics.generate_latest().decode("ascii")
        self.assertIn(
            'maas_node_mem_MemTotal{service_type="rack"} 123.0', output
        )
        self.assertIn(
            'maas_node_mem_SwapCached{service_type="rack"} 456.0', output
        )
        self.assertIn(
            'maas_node_mem_VmallocUsed{service_type="rack"} 789.0', output
        )
        self.assertIn(
            'maas_node_mem_HugePages_Total{service_type="rack"} 321.0', output
        )


class TestUpdateCPUMetrics(MAASTestCase):
    def test_update_metrics(self):
        self.patch(metrics, "GLOBAL_LABELS", {"service_type": "rack"})
        tempdir = self.useFixture(TempDirectory())
        stat = Path(tempdir.path) / "stat"
        stat.write_text(
            dedent(
                """\
            cpu  111 222 333 444 555 666 7 888 9 11
            cpu0 222 333 444 555 666 777 8 999 1 22
            cpu1 222 333 444 555 666 777 8 999 1 22
            other line
            other line
            """
            )
        )
        prometheus_metrics = create_metrics(
            node_metrics_definitions(),
            registry=prometheus_client.CollectorRegistry(),
        )
        update_cpu_metrics(prometheus_metrics, path=stat)
        output = prometheus_metrics.generate_latest().decode("ascii")
        self.assertIn(
            'maas_node_cpu_time{service_type="rack",state="user"} 1.11', output
        )
        self.assertIn(
            'maas_node_cpu_time{service_type="rack",state="nice"} 2.22', output
        )
        self.assertIn(
            'maas_node_cpu_time{service_type="rack",state="system"} 3.33',
            output,
        )
        self.assertIn(
            'maas_node_cpu_time{service_type="rack",state="idle"} 4.44', output
        )
        self.assertIn(
            'maas_node_cpu_time{service_type="rack",state="iowait"} 5.55',
            output,
        )
        self.assertIn(
            'maas_node_cpu_time{service_type="rack",state="irq"} 6.66', output
        )
        self.assertIn(
            'maas_node_cpu_time{service_type="rack",state="softirq"} 0.07',
            output,
        )
        self.assertIn(
            'maas_node_cpu_time{service_type="rack",state="steal"} 8.88',
            output,
        )
        self.assertIn(
            'maas_node_cpu_time{service_type="rack",state="guest"} 0.09',
            output,
        )
        self.assertIn(
            'maas_node_cpu_time{service_type="rack",state="guest_nice"} 0.11',
            output,
        )
