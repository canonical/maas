from pathlib import Path
from textwrap import dedent

from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase
import prometheus_client
from provisioningserver.prometheus.collectors import (
    CPU_TIME_FIELDS,
    MEMINFO_FIELDS,
    node_metrics_definitions,
    update_cpu_metrics,
    update_memory_metrics,
)
from provisioningserver.prometheus.utils import create_metrics


class TestNodeMetricsDefinitions(MAASTestCase):

    def test_definitions(self):
        definitions = node_metrics_definitions()
        metrics_count = len(MEMINFO_FIELDS) + len(CPU_TIME_FIELDS)
        self.assertEqual(len(definitions), metrics_count)
        for definition in definitions:
            self.assertEqual('Gauge', definition.type)


class TestUpdateMemoryMetrics(MAASTestCase):

    def test_update_metrics(self):
        tempdir = self.useFixture(TempDirectory())
        meminfo = (Path(tempdir.path) / 'meminfo')
        meminfo.write_text(dedent(
            '''\
            MemTotal:         123 Kb
            SwapCached:       456 Kb
            VmallocUsed:      789 Kb
            HugePages_Total:  321
            '''))
        prometheus_metrics = create_metrics(
            node_metrics_definitions(),
            registry=prometheus_client.CollectorRegistry())
        update_memory_metrics(prometheus_metrics, path=meminfo)
        output = prometheus_metrics.generate_latest().decode('ascii')
        self.assertIn('maas_node_mem_MemTotal 123.0', output)
        self.assertIn('maas_node_mem_SwapCached 456.0', output)
        self.assertIn('maas_node_mem_VmallocUsed 789.0', output)
        self.assertIn('maas_node_mem_HugePages_Total 321.0', output)


class TestUpdateCPUMetrics(MAASTestCase):

    def test_update_metrics(self):
        tempdir = self.useFixture(TempDirectory())
        stat = (Path(tempdir.path) / 'stat')
        stat.write_text(dedent(
            '''\
            cpu  111 222 333 444 555 666 7 888 9 11
            cpu0 222 333 444 555 666 777 8 999 1 22
            cpu1 222 333 444 555 666 777 8 999 1 22
            other line
            other line
            '''))
        prometheus_metrics = create_metrics(
            node_metrics_definitions(),
            registry=prometheus_client.CollectorRegistry())
        update_cpu_metrics(prometheus_metrics, path=stat)
        output = prometheus_metrics.generate_latest().decode('ascii')
        self.assertIn('maas_node_cpu_time_user 111.0', output)
        self.assertIn('maas_node_cpu_time_nice 222.0', output)
        self.assertIn('maas_node_cpu_time_system 333.0', output)
        self.assertIn('maas_node_cpu_time_idle 444.0', output)
        self.assertIn('maas_node_cpu_time_iowait 555.0', output)
        self.assertIn('maas_node_cpu_time_irq 666.0', output)
        self.assertIn('maas_node_cpu_time_softirq 7.0', output)
        self.assertIn('maas_node_cpu_time_steal 888.0', output)
        self.assertIn('maas_node_cpu_time_guest 9.0', output)
        self.assertIn('maas_node_cpu_time_guest_nice 11.0', output)
