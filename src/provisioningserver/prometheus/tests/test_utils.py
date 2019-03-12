import atexit

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
        definitions = [
            MetricDefinition('Gauge', 'a_gauge', 'A Gauge', ['foo', 'bar'])
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry())
        prometheus_metrics.update(
            'a_gauge', 'set', value=22, labels={'foo': 'FOO', 'bar': 'BAR'})
        self.assertIn(
            'a_gauge{bar="BAR",foo="FOO"} 22.0',
            prometheus_metrics.generate_latest().decode('ascii'))

    def test_update_with_extra_labels(self):
        definitions = [
            MetricDefinition('Gauge', 'a_gauge', 'A Gauge', ['foo', 'bar'])
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            extra_labels={'baz': 'BAZ', 'bza': 'BZA'},
            registry=prometheus_client.CollectorRegistry())
        prometheus_metrics.update(
            'a_gauge', 'set', value=22, labels={'foo': 'FOO', 'bar': 'BAR'})
        self.assertIn(
            'a_gauge{bar="BAR",baz="BAZ",bza="BZA",foo="FOO"} 22.0',
            prometheus_metrics.generate_latest().decode('ascii'))

    def test_with_update_handlers(self):
        def update_gauge(metrics):
            metrics.update('a_gauge', 'set', value=33)

        prometheus_metrics = PrometheusMetrics(
            definitions=[MetricDefinition('Gauge', 'a_gauge', 'A Gauge', [])],
            update_handlers=[update_gauge],
            registry=prometheus_client.CollectorRegistry())
        self.assertIn(
            'a_gauge 33.0',
            prometheus_metrics.generate_latest().decode('ascii'))

    def test_register_atexit_global_registry(self):
        mock_register = self.patch(atexit, 'register')
        definitions = [
            MetricDefinition('Gauge', 'a_gauge', 'A Gauge', ['foo', 'bar'])
        ]
        prometheus_metrics = PrometheusMetrics(definitions=definitions)
        mock_register.assert_called_once_with(
            prometheus_metrics._cleanup_metric_files)

    def test_no_register_atexit_custom_registry(self):
        mock_register = self.patch(atexit, 'register')
        definitions = [
            MetricDefinition('Gauge', 'a_gauge', 'A Gauge', ['foo', 'bar'])
        ]
        PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry())
        mock_register.assert_not_called()

    @inlineCallbacks
    def test_record_call_latency_async(self):
        definitions = [
            MetricDefinition(
                'Histogram', 'histo', 'An histogram', ['foo', 'bar'])
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry())
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

    def test_record_call_latency_sync(self):
        definitions = [
            MetricDefinition(
                'Histogram', 'histo', 'An histogram', ['foo', 'bar'])
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry())
        label_call_args = []

        def get_labels(*args, **kwargs):
            label_call_args.append((args, kwargs))
            return {'foo': 'FOO', 'bar': 'BAR'}

        @prometheus_metrics.record_call_latency('histo', get_labels=get_labels)
        def func(param1, param2=None):
            return param1

        obj = object()
        result = func(obj, param2='baz')
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
        prometheus_metrics = create_metrics(
            self.metrics_definitions,
            registry=prometheus_client.CollectorRegistry())
        self.assertIsInstance(prometheus_metrics, PrometheusMetrics)
        self.assertCountEqual(
            prometheus_metrics.available_metrics,
            ['sample_counter', 'sample_histogram'])

    def test_metrics_prometheus_not_availble(self):
        self.patch(utils, 'PROMETHEUS_SUPPORTED', False)
        prometheus_metrics = create_metrics(
            self.metrics_definitions,
            registry=prometheus_client.CollectorRegistry())
        self.assertEqual(prometheus_metrics.available_metrics, [])

    def test_extra_labels(self):
        prometheus_metrics = create_metrics(
            self.metrics_definitions,
            extra_labels={'foo': 'FOO', 'bar': 'BAR'},
            registry=prometheus_client.CollectorRegistry())
        prometheus_metrics.update('sample_counter', 'inc')
        content = prometheus_metrics.generate_latest().decode('ascii')
        self.assertIn('sample_counter{bar="BAR",foo="FOO"} 1.0', content)

    def test_extra_labels_callable(self):
        values = ['a', 'b']
        prometheus_metrics = create_metrics(
            self.metrics_definitions, extra_labels={'foo': values.pop},
            registry=prometheus_client.CollectorRegistry())
        prometheus_metrics.update('sample_counter', 'inc')
        prometheus_metrics.update('sample_counter', 'inc')
        content = prometheus_metrics.generate_latest().decode('ascii')
        self.assertIn('sample_counter{foo="a"} 1.0', content)
        self.assertIn('sample_counter{foo="b"} 1.0', content)
