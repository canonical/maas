import asyncio
import os
from subprocess import Popen

import prometheus_client
import pytest
from twisted.internet.defer import inlineCallbacks, returnValue

from provisioningserver.prometheus.utils import (
    clean_prometheus_dir,
    create_metrics,
    MetricDefinition,
    PrometheusMetrics,
)


class TestPrometheusMetricsNew:
    def test_empty(self):
        prometheus_metrics = PrometheusMetrics()
        assert prometheus_metrics.available_metrics == []
        assert prometheus_metrics.generate_latest() is None

    def test_update_empty(self):
        prometheus_metrics = PrometheusMetrics()
        prometheus_metrics.update("some_metric", "inc")
        assert prometheus_metrics.generate_latest() is None

    def test_update(self):
        definitions = [
            MetricDefinition("Gauge", "a_gauge", "A Gauge", ["foo", "bar"])
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry(),
        )
        prometheus_metrics.update(
            "a_gauge", "set", value=22, labels={"foo": "FOO", "bar": "BAR"}
        )
        assert (
            'a_gauge{bar="BAR",foo="FOO"} 22.0'
            in prometheus_metrics.generate_latest().decode("ascii")
        )

    def test_update_call_value_class(self):
        definitions = [MetricDefinition("Counter", "a_counter", "A Counter")]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry(),
        )
        prometheus_metrics.update("a_counter", "set", value=22)
        assert (
            "a_counter_total 22.0"
            in prometheus_metrics.generate_latest().decode("ascii")
        )

    def test_update_with_extra_labels(self):
        definitions = [
            MetricDefinition("Gauge", "a_gauge", "A Gauge", ["foo", "bar"])
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            extra_labels={"baz": "BAZ", "bza": "BZA"},
            registry=prometheus_client.CollectorRegistry(),
        )
        prometheus_metrics.update(
            "a_gauge", "set", value=22, labels={"foo": "FOO", "bar": "BAR"}
        )
        assert (
            'a_gauge{bar="BAR",baz="BAZ",bza="BZA",foo="FOO"} 22.0'
            in prometheus_metrics.generate_latest().decode("ascii")
        )

    def test_with_update_handlers(self):
        def update_gauge(metrics):
            metrics.update("a_gauge", "set", value=33)

        prometheus_metrics = PrometheusMetrics(
            definitions=[MetricDefinition("Gauge", "a_gauge", "A Gauge", [])],
            update_handlers=[update_gauge],
            registry=prometheus_client.CollectorRegistry(),
        )
        assert "a_gauge 33.0" in prometheus_metrics.generate_latest().decode(
            "ascii"
        )

    @pytest.mark.asyncio
    async def test_record_call_latency_deferred(self):
        definitions = [
            MetricDefinition(
                "Histogram", "histo", "An histogram", ["foo", "bar"]
            )
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry(),
        )
        label_call_args = []

        def get_labels(*args, **kwargs):
            label_call_args.append((args, kwargs))
            return {"foo": "FOO", "bar": "BAR"}

        @prometheus_metrics.record_call_latency("histo", get_labels=get_labels)
        @inlineCallbacks
        def func(param1, param2=None):
            yield
            returnValue(param1)

        obj = object()
        result = await func(obj, param2="baz")
        assert result is obj
        # the get_labels function is called with the same args as the function
        assert label_call_args == [((obj,), {"param2": "baz"})]
        assert (
            'histo_count{bar="BAR",foo="FOO"} 1.0'
            in prometheus_metrics.generate_latest().decode("ascii")
        )

    @pytest.mark.asyncio
    async def test_record_call_latency_asyncio(self):
        definitions = [
            MetricDefinition(
                "Histogram", "histo", "An histogram", ["foo", "bar"]
            )
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry(),
        )
        label_call_args = []

        def get_labels(*args, **kwargs):
            label_call_args.append((args, kwargs))
            return {"foo": "FOO", "bar": "BAR"}

        @prometheus_metrics.record_call_latency("histo", get_labels=get_labels)
        async def func(param1, param2=None):
            await asyncio.sleep(0.001)
            return param1

        obj = object()
        result = await func(obj, param2="baz")
        assert result is obj
        # the get_labels function is called with the same args as the function
        assert label_call_args == [((obj,), {"param2": "baz"})]
        assert (
            'histo_count{bar="BAR",foo="FOO"} 1.0'
            in prometheus_metrics.generate_latest().decode("ascii")
        )

    def test_record_call_latency_sync(self):
        definitions = [
            MetricDefinition(
                "Histogram", "histo", "An histogram", ["foo", "bar"]
            )
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry(),
        )
        label_call_args = []

        def get_labels(*args, **kwargs):
            label_call_args.append((args, kwargs))
            return {"foo": "FOO", "bar": "BAR"}

        @prometheus_metrics.record_call_latency("histo", get_labels=get_labels)
        def func(param1, param2=None):
            return param1

        obj = object()
        result = func(obj, param2="baz")
        assert result is obj
        # the get_labels function is called with the same args as the function
        assert label_call_args == [((obj,), {"param2": "baz"})]
        assert (
            'histo_count{bar="BAR",foo="FOO"} 1.0'
            in prometheus_metrics.generate_latest().decode("ascii")
        )

    def test_failure_counter_increments_counter_on_exception(self):
        definitions = [
            MetricDefinition(
                "Counter", "test_failure", "A counter", ["foo", "bar"]
            )
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry(),
        )
        label_call_args = []

        def get_labels(*args, **kwargs):
            label_call_args.append((args, kwargs))
            return {"foo": "FOO", "bar": "BAR"}

        @prometheus_metrics.failure_counter(
            "test_failure", get_labels=get_labels
        )
        def func(param1, param2=None):
            raise Exception()

        obj = object()
        with pytest.raises(Exception):
            func(obj, param2="baz")
        assert (
            'test_failure_total{bar="BAR",foo="FOO"} 1.0'
            in prometheus_metrics.generate_latest().decode("ascii")
        )
        assert label_call_args == [((obj,), {"param2": "baz"})]

    def test_failure_counter_increments_with_a_specific_exception(self):
        class FailureCounterTestException(Exception):
            ...

        definitions = [
            MetricDefinition(
                "Counter", "test_failure", "A counter", ["foo", "bar"]
            )
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry(),
        )
        label_call_args = []

        def get_labels(*args, **kwargs):
            label_call_args.append((args, kwargs))
            return {"foo": "FOO", "bar": "BAR"}

        @prometheus_metrics.failure_counter(
            "test_failure",
            exceptions_filter=(FailureCounterTestException,),
            get_labels=get_labels,
        )
        def func1(param1, param2=None):
            raise FailureCounterTestException()

        @prometheus_metrics.failure_counter(
            "test_failure",
            exceptions_filter=(FailureCounterTestException,),
            get_labels=get_labels,
        )
        def func2(param1, param2=None):
            raise Exception()

        obj = object()
        with pytest.raises(FailureCounterTestException):
            func1(obj, param2="baz")

        with pytest.raises(Exception):
            func2(obj, param2="baz")

        with pytest.raises(FailureCounterTestException):
            func1(obj, param2="baz")
        results = prometheus_metrics.generate_latest().decode("ascii")
        assert 'test_failure_total{bar="BAR",foo="FOO"} 2.0' in results
        assert 'test_failure_total{bar="BAR",foo="FOO"} 3.0' not in results
        assert label_call_args == [
            ((obj,), {"param2": "baz"}),
            ((obj,), {"param2": "baz"}),
            ((obj,), {"param2": "baz"}),
        ]

    def test_failure_counter_does_not_increment_on_success(self):
        definitions = [
            MetricDefinition(
                "Counter", "test_failure", "A counter", ["foo", "bar"]
            )
        ]
        prometheus_metrics = PrometheusMetrics(
            definitions=definitions,
            registry=prometheus_client.CollectorRegistry(),
        )
        label_call_args = []

        def get_labels(*args, **kwargs):
            label_call_args.append((args, kwargs))
            return {"foo": "FOO", "bar": "BAR"}

        @prometheus_metrics.failure_counter(
            "test_failure", get_labels=get_labels
        )
        def func(param1, param2=None):
            return param1

        obj = object()
        result = func(obj, param2="baz")
        assert obj is result
        assert label_call_args == [((obj,), {"param2": "baz"})]


class TestCreateMetrics:
    METRICS_DEFINITIONS = [
        MetricDefinition(
            "Histogram", "sample_histogram", "Sample histogram", []
        ),
        MetricDefinition("Counter", "sample_counter", "Sample counter", []),
    ]

    def test_metrics(self):
        prometheus_metrics = create_metrics(
            self.METRICS_DEFINITIONS,
            registry=prometheus_client.CollectorRegistry(),
        )
        assert isinstance(prometheus_metrics, PrometheusMetrics)
        assert set(prometheus_metrics.available_metrics) == {
            "sample_counter",
            "sample_histogram",
        }

    def test_extra_labels(self):
        prometheus_metrics = create_metrics(
            self.METRICS_DEFINITIONS,
            extra_labels={"foo": "FOO", "bar": "BAR"},
            registry=prometheus_client.CollectorRegistry(),
        )
        prometheus_metrics.update("sample_counter", "inc")
        content = prometheus_metrics.generate_latest().decode("ascii")
        assert 'sample_counter_total{bar="BAR",foo="FOO"} 1.0' in content

    def test_extra_labels_callable(self):
        values = ["a", "b"]
        prometheus_metrics = create_metrics(
            self.METRICS_DEFINITIONS,
            extra_labels={"foo": values.pop},
            registry=prometheus_client.CollectorRegistry(),
        )
        prometheus_metrics.update("sample_counter", "inc")
        prometheus_metrics.update("sample_counter", "inc")
        content = prometheus_metrics.generate_latest().decode("ascii")
        assert 'sample_counter_total{foo="a"} 1.0' in content
        assert 'sample_counter_total{foo="b"} 1.0' in content


class TestCleanPrometheusDir:
    def get_unused_pid(self):
        """Return a PID for a process that has just finished running."""
        proc = Popen(["/bin/true"])
        proc.wait()
        return proc.pid

    def test_dir_not_existent(self):
        assert clean_prometheus_dir("/not/here") is None

    def test_env_not_specified(self, monkeypatch):
        monkeypatch.delenv("prometheus_multiproc_dir", raising=False)
        assert clean_prometheus_dir() is None

    def test_env_dir_not_existent(self, monkeypatch):
        monkeypatch.setenv("prometheus_multiproc_dir", "/not/here")
        assert clean_prometheus_dir() is None

    def test_delete_for_nonexistent_processes(self, tmp_path):
        pid = os.getpid()
        file1 = tmp_path / "histogram_1.db"
        file1.touch()
        file2 = tmp_path / f"histogram_{pid}.db"
        file2.touch()
        file3 = tmp_path / f"histogram_{self.get_unused_pid()}.db"
        file3.touch()
        file4 = tmp_path / f"histogram_{self.get_unused_pid()}.db"
        file4.touch()
        clean_prometheus_dir(str(tmp_path))
        assert file1.exists()
        assert file2.exists()
        assert not file3.exists()
        assert not file4.exists()

    def test_delete_file_disappeared(self, mocker, tmp_path):
        real_os_remove = os.remove

        def mock_os_remove(path):
            # remove it twice, so that FileNotFoundError is raised
            real_os_remove(path)
            real_os_remove(path)

        mocker.patch.object(os, "remove", mock_os_remove)
        file1 = tmp_path / f"histogram_{self.get_unused_pid()}.db"
        file1.touch()
        assert clean_prometheus_dir(str(tmp_path)) is None
