from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
import prometheus_client
from provisioningserver.prometheus import utils
from provisioningserver.prometheus.utils import (
    create_metrics,
    MetricDefinition,
    PrometheusMetrics,
)
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
)


class TestPrometheusMetrics(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_empty(self):
        prometheus_metrics = PrometheusMetrics()
        self.assertEqual(prometheus_metrics.available_metrics, [])
        self.assertIsNone(prometheus_metrics.generate_latest())

    def test_update_empty(self):
        prometheus_metrics = PrometheusMetrics()
        prometheus_metrics.update('some_metric', 'inc')
        self.assertIsNone(prometheus_metrics.generate_latest())

    def test_update(self):
        registry = prometheus_client.CollectorRegistry()
        metric = prometheus_client.Gauge(
            'a_gauge', 'A Gauge', ['foo', 'bar'], registry=registry)
        prometheus_metrics = PrometheusMetrics(
            registry=registry, metrics={'a_gauge': metric})
        prometheus_metrics.update(
            'a_gauge', 'set', value=22, labels={'foo': 'FOO', 'bar': 'BAR'})
        self.assertIn(
            'a_gauge{bar="BAR",foo="FOO"} 22.0',
            prometheus_metrics.generate_latest().decode('ascii'))

    @inlineCallbacks
    def test_record_call_latency(self):
        registry = prometheus_client.CollectorRegistry()
        metric = prometheus_client.Histogram(
            'histo', 'An histogram', ['foo', 'bar'], registry=registry)
        prometheus_metrics = PrometheusMetrics(
            registry=registry, metrics={'histo': metric})

        label_call_args = []

        def get_labels(*args, **kwargs):
            label_call_args.append((args, kwargs))
            return {'foo': 'FOO', 'bar': 'BAR'}

        @prometheus_metrics.record_call_latency('histo', get_labels=get_labels)
        @inlineCallbacks
        def func(param1, param2=None):
            yield
            returnValue(param1)

        obj = object()
        result = yield func(obj, param2='baz')
        self.assertIs(result, obj)
        # the get_labels function is called with the same args as the function
        self.assertEqual(label_call_args, [((obj,), {'param2': 'baz'})])
        self.assertIn(
            'histo_count{bar="BAR",foo="FOO"} 1.0',
            prometheus_metrics.generate_latest().decode('ascii'))


class TestCreateMetrics(MAASTestCase):

    def setUp(self):
        super().setUp()
        self.metrics_definitions = [
            MetricDefinition(
                'Histogram', 'sample_histogram', 'Sample histogram', []),
            MetricDefinition(
                'Counter', 'sample_counter', 'Sample counter', [])]

    def test_metrics(self):
        prometheus_metrics = create_metrics(self.metrics_definitions)
        self.assertIsInstance(prometheus_metrics, PrometheusMetrics)
        self.assertCountEqual(
            prometheus_metrics.available_metrics,
            ['sample_counter', 'sample_histogram'])

    def test_metrics_prometheus_not_availble(self):
        self.patch(utils, 'PROMETHEUS_SUPPORTED', False)
        prometheus_metrics = create_metrics(self.metrics_definitions)
        self.assertEqual(prometheus_metrics.available_metrics, [])
