from pathlib import Path
from textwrap import dedent

from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase
import prometheus_client
from provisioningserver.prometheus.collectors import (
    MEMINFO_FIELDS,
    memory_metrics_definitions,
    update_memory_metrics,
)
from provisioningserver.prometheus.utils import create_metrics


class TestMemoryMetricsDefinitions(MAASTestCase):

    def test_definitions(self):
        definitions = memory_metrics_definitions()
        self.assertEqual(len(definitions), len(MEMINFO_FIELDS))
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
            memory_metrics_definitions(),
            registry=prometheus_client.CollectorRegistry())
        update_memory_metrics(prometheus_metrics, path=meminfo)
        output = prometheus_metrics.generate_latest().decode('ascii')
        self.assertIn('maas_node_mem_MemTotal 123.0', output)
        self.assertIn('maas_node_mem_SwapCached 456.0', output)
        self.assertIn('maas_node_mem_VmallocUsed 789.0', output)
        self.assertIn('maas_node_mem_HugePages_Total 321.0', output)
