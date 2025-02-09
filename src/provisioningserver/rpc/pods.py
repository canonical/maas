# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Pod RPC functions."""

import json

from twisted.internet.defer import Deferred, ensureDeferred, NotACoroutineError
from twisted.internet.threads import deferToThread

from provisioningserver.drivers.pod import (
    DiscoveredCluster,
    DiscoveredMachine,
    DiscoveredPod,
    DiscoveredPodHints,
    DiscoveredPodProject,
    get_error_message,
)
from provisioningserver.drivers.pod.registry import PodDriverRegistry
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.refresh.maas_api_helper import (
    Credentials,
    signal,
    SignalException,
)
from provisioningserver.rpc.exceptions import (
    PodActionFail,
    PodInvalidResources,
    UnknownPodType,
)
from provisioningserver.utils.twisted import asynchronous

maaslog = get_maas_logger("pod")
log = LegacyLogger()


@asynchronous
def discover_pod_projects(pod_type, context):
    """Discover projects in the specified pod."""
    pod_driver = PodDriverRegistry.get_item(pod_type)
    if pod_driver is None:
        raise UnknownPodType(pod_type)

    # there's no database ID for the pod yet as it's not register. The ID is
    # only used for logging, so we pass 0 to distinguish from existing pods.
    d = ensureDeferred(pod_driver.discover_projects(0, context))

    def convert(projects):
        return {
            "projects": [
                DiscoveredPodProject(
                    name=project["name"], description=project["description"]
                )
                for project in projects
            ]
        }

    d.addCallback(convert)
    d.addErrback(
        convert_errors, log_message="Failed to discover VM host projects."
    )
    return d


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
    except NotACoroutineError:
        raise PodActionFail(  # noqa: B904
            "bad pod driver '%s'; 'discover' did not return Deferred."
            % pod_type
        )

    def convert(result):
        """Convert the result to send over RPC."""
        if result is None:
            raise PodActionFail("unable to discover pod information.")
        elif isinstance(result, DiscoveredCluster):
            return {"cluster": result}
        elif not isinstance(result, DiscoveredPod):
            raise PodActionFail(
                "bad pod driver '%s'; 'discover' returned invalid result."
                % pod_type
            )
        else:
            return {"pod": result}

    d.addCallback(convert)
    d.addErrback(convert_errors, log_message="Failed to discover VM host.")
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

    d.addCallback(convert)
    d.addErrback(
        convert_errors,
        log_message=f"{name}: Failed to compose machine: {request}",
        keep_failures=[PodInvalidResources],
    )
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
    try:
        d = ensureDeferred(pod_driver.get_commissioning_data(pod_id, context))
    except NotACoroutineError:
        raise PodActionFail(  # noqa: B904
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
                    credentials=Credentials(
                        token_key=token_key,
                        token_secret=token_secret,
                        consumer_key=consumer_key,
                    ),
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
                raise PodActionFail(  # noqa: B904
                    f"Unable to send Pod commissioning information for {name}({system_id}): {e}"
                )

    d.addCallback(
        lambda commissioning_results: deferToThread(
            send_items, commissioning_results
        )
    )
    d.addCallback(lambda _: {})
    d.addErrback(
        convert_errors, log_message="Failed to send_pod_commissioning_results."
    )
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

    d.addCallback(convert)
    d.addErrback(convert_errors, log_message="Failed to decompose machine.")
    return d


def convert_errors(failure, log_message=None, keep_failures=None):
    """Convert all failures into PodActionFail unless already a
    PodActionFail or NotImplementedError.

    Optionally, also log a failure message.
    """
    valid_failures = [NotImplementedError, PodActionFail]
    if keep_failures:
        valid_failures.extend(keep_failures)
    if log_message:
        log.err(failure, log_message)
    if failure.check(*valid_failures):
        return failure
    else:
        raise PodActionFail(get_error_message(failure.value))
