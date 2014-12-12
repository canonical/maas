# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Django Debug Toolbar Panel

This panel records all of the RPC calls that are made during
a Django request. Use this panel to make sure not to many RPC
calls are made per request.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
]

from collections import defaultdict
import time
import traceback

from crochet import EventualResult
from debug_toolbar.panels import Panel
from maasserver import eventloop
from maasserver.models import NodeGroup
from twisted.internet.defer import Deferred


class EventualResultRecorder:

    def __init__(self, result, cluster_uuid, rpc_panel, rpc_call):
        self._result = result
        self._cluster_uuid = cluster_uuid
        self._rpc_panel = rpc_panel
        self._rpc_call = rpc_call

    def __getattribute__(self, name):
        if name in [
                '_result', '_cluster_uuid',
                '_rpc_panel', '_rpc_call', 'wait']:
            return object.__getattribute__(self, name)
        return self._result.__getattribute__(name)

    def wait(self, timeout=None):
        """Wait for the result.

        Records the amount of time passed until result is returned.
        """
        start_time = time.time()
        try:
            final_result = self._result.wait(timeout=timeout)
        except Exception as e:
            # Record the RPC call as an error.
            end_time = time.time()
            self._rpc_call['error'] = '%s' % e
            self._rpc_call['traceback'] = traceback.format_exc()
            self._rpc_call['time'] = end_time - start_time
            self._rpc_panel.cluster_calls[self._cluster_uuid].append(
                self._rpc_call)
            raise

        # Record the valid RPC response.
        end_time = time.time()
        self._rpc_call['result'] = final_result
        self._rpc_call['time'] = end_time - start_time
        self._rpc_panel.cluster_calls[self._cluster_uuid].append(
            self._rpc_call)
        return final_result


class ClientRecorder:

    def __init__(self, client, cluster_uuid, rpc_panel):
        self._client = client
        self._cluster_uuid = cluster_uuid
        self._rpc_panel = rpc_panel

    def __getattribute__(self, name):
        if name in ['_client', '_cluster_uuid', '_rpc_panel', '__call__']:
            return object.__getattribute__(self, name)
        return self._client.__getattribute__(name)

    def __call__(self, cmd, *args, **kwargs):
        """Execute the RPC command.

        Tracks the command, arguments, result, and timing of the call.
        """
        d = self._client(cmd, *args, **kwargs)

        # The client can either return a Deferred or an EventualResult. Each
        # one is handled differently.
        if isinstance(d, EventualResult):
            # Wrap the EventualResult so we can track its result and time.
            return EventualResultRecorder(
                d, self._cluster_uuid, self._rpc_panel, {
                    'command': cmd,
                    'arguments': kwargs,
                    })
        elif isinstance(d, Deferred):
            # Add a callback on the deferred to register the timing of
            # the call.

            def success_result(result):
                end_time = time.time()
                self._rpc_panel.cluster_calls[self._cluster_uuid].append({
                    'command': cmd,
                    'arguments': kwargs,
                    'result': result,
                    'time': end_time - start_time,
                    })
                return result

            def failure_result(failure):
                end_time = time.time()
                self._rpc_panel.cluster_calls[self._cluster_uuid].append({
                    'command': cmd,
                    'arguments': kwargs,
                    'error': failure.getErrorMessage(),
                    'traceback': failure.getTraceback(),
                    'time': end_time - start_time,
                    })
                return failure

            start_time = time.time()
            d.addCallbacks(success_result, failure_result)
        return d


class RegionServiceRecorder:

    def __init__(self, original_service, rpc_panel):
        self._original_service = original_service
        self._rpc_panel = rpc_panel

    def __getattribute__(self, name):
        if name in ['_original_service', '_rpc_panel', 'getClientFor']:
            return object.__getattribute__(self, name)
        return self._original_service.__getattribute__(name)

    def getClientFor(self, uuid, timeout=30):
        """Get the RPC client for cluster with uuid.

        Wraps the returned client in `ClientRecorder` allowing tracking
        of all RPC calls on the client.
        """
        d = self._original_service.getClientFor(uuid, timeout=timeout)
        self._rpc_panel.cluster_getClientFor_call_count[uuid] += 1

        def wrap_with_recorder(client):
            return ClientRecorder(client, uuid, self._rpc_panel)

        def log_no_connection(failure):
            self._rpc_panel.cluster_getClientFor_errors[uuid].append({
                'error': failure.getErrorMessage(),
                'traceback': failure.getTraceback(),
                })
            return failure

        d.addCallbacks(wrap_with_recorder, log_no_connection)
        return d


class RPCPanel(Panel):
    """
    A panel to display all RPC calls made during a request.
    """
    template = 'maasserver/debug_rpc_toolbar.html'

    nav_title = "RPC"
    title = "Twisted RPC Calls"

    def __init__(self, *args, **kwargs):
        super(RPCPanel, self).__init__(*args, **kwargs)
        self.cluster_calls = defaultdict(list)
        self.cluster_getClientFor_call_count = defaultdict(int)
        self.cluster_getClientFor_errors = defaultdict(list)

    @property
    def nav_subtitle(self):
        total_rpc_calls, _, _, total_time = (
            self.get_call_statistics())
        return "%d call in %.2fms" % (total_rpc_calls, total_time)

    def enable_instrumentation(self):
        """Turn on RPC tracking."""
        try:
            original_service = eventloop.services.getServiceNamed("rpc")
        except KeyError:
            # The rpc service has not started so nothing can be done to
            # enable the instrumentation.
            return
        eventloop.services.namedServices["rpc"] = (
            RegionServiceRecorder(original_service, self))

    def disable_instrumentation(self):
        """Disable RPC tracking."""
        try:
            service_recorder = eventloop.services.getServiceNamed("rpc")
        except KeyError:
            # The rpc service has not started so nothing can be done to
            # enable the instrumentation.
            return
        try:
            eventloop.services.namedServices["rpc"] = (
                service_recorder._original_service)
        except AttributeError:
            # This means that the service_recorder is actually the original
            # service. This occurs when enable_instrumentation is called before
            # the rpc service is started, and disable_instrumentation is called
            # after the rpc service has started.
            pass

    def build_getClientFor_errors_for_template(self):
        """Return list used for rendering the getClientFor errors in the
        template."""
        template_errors = []
        clusters = NodeGroup.objects.filter(
            uuid__in=self.cluster_getClientFor_errors.keys())
        for uuid, errors in self.cluster_getClientFor_errors.items():
            cluster = clusters.get(uuid=uuid)
            for error in errors:
                template_errors.append({
                    'uuid': cluster.uuid,
                    'cluster': cluster.name,
                    'error': error['error'],
                    'traceback': error['traceback'],
                    })
        return template_errors

    def build_calls_for_template(self):
        """Return list of succeed and fail RPC calls used for rendering
        in the template."""
        succeed_calls = []
        fail_calls = []
        clusters = NodeGroup.objects.filter(
            uuid__in=self.cluster_calls.keys())
        for uuid, calls in self.cluster_calls.items():
            cluster = clusters.get(uuid=uuid)
            for call in calls:
                template_call = {
                    'uuid': cluster.uuid,
                    'cluster': cluster.name,
                    'command': call['command'].__name__,
                    'arguments': call['arguments'],
                    'time': call['time']
                    }
                if 'result' in call:
                    template_call['result'] = call['result']
                    succeed_calls.append(template_call)
                else:
                    template_call['error'] = call['error']
                    template_call['traceback'] = call['traceback']
                    fail_calls.append(template_call)
        return succeed_calls, fail_calls

    def get_call_statistics(self):
        """Return total # of rpc calls, # of succeed, # of fail, total time."""
        total_calls = 0
        total_succeed = 0
        total_fail = 0
        total_time = 0
        for calls in self.cluster_calls.values():
            for call in calls:
                total_calls += 1
                total_time += call['time']
                if 'result' in call:
                    total_succeed += 1
                else:
                    total_fail += 1
        return total_calls, total_succeed, total_fail, total_time

    def process_response(self, request, response):
        """Output the RPC calls for this request/response."""
        total_rpc_calls, total_rpc_succeed, total_rpc_fail, total_time = (
            self.get_call_statistics())
        clusters = set(
            self.cluster_getClientFor_errors.keys() +
            self.cluster_calls.keys())
        total_getClientFor_calls = sum([
            count
            for _, count in self.cluster_getClientFor_call_count.items()
            ])
        total_getClientFor_errors = sum([
            len(errors)
            for _, errors in self.cluster_getClientFor_errors.items()
            ])
        succeed_rpc_calls, fail_rpc_calls = self.build_calls_for_template()
        self.record_stats({
            'total_clusters': len(clusters),
            'total_getClientFor_calls': total_getClientFor_calls,
            'total_getClientFor_errors': total_getClientFor_errors,
            'total_rpc_calls': total_rpc_calls,
            'total_rpc_succeed': total_rpc_succeed,
            'total_rpc_fail': total_rpc_fail,
            'total_time': total_time,
            'getClientFor_errors': (
                self.build_getClientFor_errors_for_template()),
            'fail_rpc_calls': fail_rpc_calls,
            'succeed_rpc_calls': succeed_rpc_calls,
        })
