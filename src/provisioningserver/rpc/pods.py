# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Pod RPC functions."""

__all__ = ["discover_pod"]

import json

from twisted.internet.defer import Deferred, ensureDeferred
from twisted.internet.threads import deferToThread

from provisioningserver.drivers.pod import (
    DiscoveredMachine,
    DiscoveredPod,
    DiscoveredPodHints,
    get_error_message,
)
from provisioningserver.drivers.pod.registry import PodDriverRegistry
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.refresh.maas_api_helper import signal, SignalException
from provisioningserver.rpc.exceptions import (
    PodActionFail,
    PodInvalidResources,
    UnknownPodType,
)
from provisioningserver.utils.twisted import asynchronous

maaslog = get_maas_logger("pod")
log = LegacyLogger()


@asynchronous
def discover_pod(pod_type, context, pod_id=None, name=None):
    """Discover all the pod information and return the result to the
    region controller.

    The region controller handles parsing the output and updating the database
    as required.
    """
    pod_driver = PodDriverRegistry.get_item(pod_type)
    if pod_driver is None:
        raise UnknownPodType(pod_type)
    try:
        d = ensureDeferred(pod_driver.discover(pod_id, context))
    except ValueError:
        raise PodActionFail(
            "bad pod driver '%s'; 'discover' did not return Deferred."
            % pod_type
        )

    def convert(result):
        """Convert the result to send over RPC."""
        if result is None:
            raise PodActionFail("unable to discover pod information.")
        elif not isinstance(result, DiscoveredPod):
            raise PodActionFail(
                "bad pod driver '%s'; 'discover' returned invalid result."
                % pod_type
            )
        else:
            return {"pod": result}

    def catch_all(failure):
        """Convert all failures into `PodActionFail` unless already a
        `PodActionFail` or `NotImplementedError`."""
        # Log locally to help debugging.
        log.err(failure, "Failed to discover pod.")
        if failure.check(NotImplementedError, PodActionFail):
            return failure
        else:
            raise PodActionFail(get_error_message(failure.value))

    d.addCallback(convert)
    d.addErrback(catch_all)
    return d


@asynchronous
def compose_machine(pod_type, context, request, pod_id, name):
    """Compose a machine that at least matches equal to or greater than
    `request`.

    The region controller handles parsing the outputed `DiscoveredMachine` and
    updating the database as required.
    """
    pod_driver = PodDriverRegistry.get_item(pod_type)
    if pod_driver is None:
        raise UnknownPodType(pod_type)
    d = pod_driver.compose(pod_id, context, request)
    if not isinstance(d, Deferred):
        raise PodActionFail(
            "bad pod driver '%s'; 'compose' did not return Deferred."
            % pod_type
        )

    def convert(result):
        """Convert the result to send over RPC."""
        if result is None:
            # None is allowed when a machine could not be composed with the
            # driver. This means it could not match the request. Returning None
            # allows the region to try another pod if available to compose
            # that machine.
            raise PodInvalidResources()
        else:
            if (
                isinstance(result, tuple)
                and len(result) == 2
                and isinstance(result[0], DiscoveredMachine)
                and isinstance(result[1], DiscoveredPodHints)
            ):
                return {"machine": result[0], "hints": result[1]}
            else:
                raise PodActionFail(
                    "bad pod driver '%s'; 'compose' returned "
                    "invalid result." % pod_type
                )

    def catch_all(failure):
        """Convert all failures into `PodActionFail` unless already a
        `PodActionFail`, `PodInvalidResources` or `NotImplementedError`."""
        if failure.check(PodInvalidResources):
            # Driver returned its own invalid resource exception instead of
            # None. Just pass this onto the region.
            return failure

        # Log locally to help debugging.
        log.err(failure, "%s: Failed to compose machine: %s" % (name, request))
        if failure.check(NotImplementedError, PodActionFail):
            return failure
        else:
            raise PodActionFail(get_error_message(failure.value))

    d.addCallback(convert)
    d.addErrback(catch_all)
    return d


@asynchronous
def send_pod_commissioning_results(
    pod_type,
    context,
    pod_id,
    name,
    system_id,
    consumer_key,
    token_key,
    token_secret,
    metadata_url,
):
    """Send commissioning results for the Pod to the region."""
    pod_driver = PodDriverRegistry.get_item(pod_type)
    if pod_driver is None:
        raise UnknownPodType(pod_type)
    d = pod_driver.get_commissioning_data(pod_id, context)
    if not isinstance(d, Deferred):
        raise PodActionFail(
            f"bad pod driver '{pod_type}'; 'get_commissioning_data' did not return Deferred."
        )

    def send_items(commissioning_results):
        for filename, content in commissioning_results.items():
            if isinstance(content, dict) or isinstance(content, list):
                content = json.dumps(content, indent=4)
            if not isinstance(content, bytes):
                content = content.encode()
            try:
                signal(
                    url=metadata_url.geturl(),
                    creds={
                        "consumer_key": consumer_key,
                        "token_key": token_key,
                        "token_secret": token_secret,
                        "consumer_secret": "",
                    },
                    status="WORKING",
                    files={
                        # UI shows combined output by default.
                        filename: content,
                        # STDOUT output is whats actually proceed.
                        f"{filename}.out": content,
                        # Clear out STDERR and results.
                        f"{filename}.err": b"",
                        f"{filename}.yaml": b"",
                    },
                    exit_status=0,
                    error=f"Finished {filename}: 0",
                )
            except SignalException as e:
                raise PodActionFail(
                    f"Unable to send Pod commissioning information for {name}({system_id}): {e.error}"
                )

    def catch_all(failure):
        """Convert all failures into `PodActionFail` unless already a
        `PodActionFail` or `NotImplementedError`."""
        # Log locally to help debugging.
        log.err(failure, "Failed to send_pod_commissioning_results.")
        if failure.check(NotImplementedError, PodActionFail):
            return failure
        else:
            raise PodActionFail(get_error_message(failure.value))

    d.addCallback(
        lambda commissioning_results: deferToThread(
            send_items, commissioning_results
        )
    )
    d.addCallback(lambda _: {})
    d.addErrback(catch_all)
    return d


@asynchronous
def decompose_machine(pod_type, context, pod_id, name):
    """Decompose a machine. The machine to delete is contained in the `context`
    just like power actions."""
    pod_driver = PodDriverRegistry.get_item(pod_type)
    if pod_driver is None:
        raise UnknownPodType(pod_type)
    d = pod_driver.decompose(pod_id, context)
    if not isinstance(d, Deferred):
        raise PodActionFail(
            "bad pod driver '%s'; 'decompose' did not return Deferred."
            % pod_type
        )

    def convert(result):
        """Convert the result to send over RPC."""
        if result is None or not isinstance(result, DiscoveredPodHints):
            raise PodActionFail(
                "bad pod driver '%s'; 'decompose' returned invalid result."
                % pod_type
            )
        else:
            return {"hints": result}

    def catch_all(failure):
        """Convert all failures into `PodActionFail` unless already a
        `PodActionFail` or `NotImplementedError`."""
        # Log locally to help debugging.
        log.err(failure, "Failed to decompose machine.")
        if failure.check(NotImplementedError, PodActionFail):
            return failure
        else:
            raise PodActionFail(get_error_message(failure.value))

    d.addCallback(convert)
    d.addErrback(catch_all)
    return d
