# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Common code for MAAS Cluster RPC operations."""

from collections import namedtuple
from functools import partial

from django.core.exceptions import ValidationError
from twisted.python.failure import Failure

from maasserver import logger
from maasserver.exceptions import ClusterUnavailable
from maasserver.models.node import RackController
from maasserver.rpc import getClientFor
from maasserver.utils import asynchronous
from provisioningserver.rpc.exceptions import NoConnectionsAvailable

RPCResults = namedtuple(
    "CallResults",
    (
        "results",
        "failures",
        "available",
        "unavailable",
        "success",
        "failed",
        "timeout",
    ),
)


def call_racks_synchronously(
    command, *, kwargs=None, timeout=10, controllers=None
):
    """Calls the specified RPC command on each rack controller synchronously.

    Collects the results into a list, then returns a `RPCResults` namedtuple
    containing details about which racks were available, unavailable, failed,
    timed out, and succeeded.

    Blocks for up to `timeout` seconds in order to connect to each rack
    controller and await the result of the call. (Therefore, this function
    should only be used when calling RPC methods which return immediately.)

    If a dictionary of `kwargs` is specified, those arguments will be passed
    to the specified command.
    """
    available_racks = []
    unavailable_racks = []
    successful_racks = []
    failed_racks = []
    timed_out_racks = []
    failures = []
    results = list(
        call_clusters(
            command,
            kwargs=kwargs,
            timeout=timeout,
            controllers=controllers,
            available_callback=available_racks.append,
            unavailable_callback=unavailable_racks.append,
            success_callback=successful_racks.append,
            failed_callback=failed_racks.append,
            failure_callback=failures.append,
            timeout_callback=timed_out_racks.append,
        )
    )
    return RPCResults(
        results,
        failures,
        available_racks,
        unavailable_racks,
        successful_racks,
        failed_racks,
        timed_out_racks,
    )


def _none(_):
    """Default no-op callback for `call_clusters()`."""
    pass


def call_clusters(
    command,
    *,
    kwargs=None,
    timeout=10,
    controllers=None,
    ignore_errors=True,
    available_callback=_none,
    unavailable_callback=_none,
    success_callback=_none,
    failed_callback=_none,
    failure_callback=_none,
    timeout_callback=_none,
):
    """Make an RPC call to all rack controllers in parallel.

    Includes optional callbacks to report the status of the call for each
    controller. If the call was a success, the `success_callback` will be
    called immediately before the response is yielded (so that the caller
    can determine which controller was contacted successfully).

    All optional callbacks are called with a single argument: the
    `RackController` model object that corresponds to the RPC call.

    :param controllers: The :class:`RackController`s on which to make the RPC
        call. If None, defaults to all :class:`RackController`s.
    :param timeout: The maximum number of seconds to wait for responses from
        all controllers.
    :param command: An :class:`amp.Command` to call on the clusters.
    :param ignore_errors: If True, errors encountered whilst calling
        `command` on the clusters won't raise an exception.
    :param available_callback: Optional callback; called with the controller
        when an RPC connection to the controller was established.
    :param unavailable_callback: Optional callback; called with the controller
        when an RPC connection to the controller failed to be established.
    :param success_callback: Optional callback; called with the controller
        when the RPC call was a success and this method is about to yield the
        result.
    :param failed_callback: Optional callback; called with the controller if
        the RPC call fails.
    :param failure_callback: Optional callback; called with the `Failure`
        object if the RPC call fail with a well-known exception.
    :param timeout_callback: Optional callback; called if the RPC call
        fails with a timeout.
    :param kwargs: Optional keyword arguments to pass to the command
    :return: A generator of results, i.e. the dicts returned by the RPC
        call.
    :raises: :py:class:`ClusterUnavailable` when a cluster is not
        connected or there's an error during the call, and errors are
        not being ignored.
    """
    # Get the name of the RPC function for logging purposes. Each RPC function
    # is enacapsulated in a `class`, so should have a corresponding `__name__`.
    # However, we don't want to crash if that isn't the case.
    if kwargs is None:
        kwargs = {}
    command_name = (
        command.commandName.decode("ascii")
        if hasattr(command, "commandName")
        else "<unknown>"
    )
    calls = {}
    if controllers is None:
        controllers = RackController.objects.all()
    for controller in controllers:
        try:
            client = getClientFor(controller.system_id)
        except NoConnectionsAvailable:
            logger.error(
                "Error while calling %s: Unable to get RPC connection for "
                "rack controller '%s' (%s).",
                command_name,
                controller.hostname,
                controller.system_id,
            )
            unavailable_callback(controller)
            if not ignore_errors:
                raise ClusterUnavailable(  # noqa: B904
                    "Unable to get RPC connection for rack controller "
                    "'%s' (%s)" % (controller.hostname, controller.system_id)
                )
        else:
            # The call to partial() requires a `callable`, but `getClientFor()`
            # might return a `Deferred` if it runs in the reactor.
            assert callable(client), (
                "call_clusters() must not be called in the reactor thread. "
                "You probably want to use deferToDatabase()."
            )
            available_callback(controller)
            call = partial(client, command, **kwargs)
            calls[call] = controller

    for call, response in asynchronous.gatherCallResults(
        calls, timeout=timeout
    ):
        # When a call returns results, figure out which controller it came from
        # and remove it from the list, so we can report which controllers
        # timed out.
        controller = calls[call]
        del calls[call]
        if isinstance(response, Failure):
            # Create a nice message for logging purposes. We can rely on
            # the 'type' ivar being filled in with the Exception type in a
            # Failure object, so use that to get a nice version of the name.
            exception_class = response.type.__name__
            error = str(response.value).strip()
            if len(error) > 0:
                error = ": " + error
            human_readable_error = (
                "Exception during %s() on rack controller '%s' (%s): %s%s"
                % (
                    command_name,
                    controller.hostname,
                    controller.system_id,
                    exception_class,
                    error,
                )
            )
            logger.warning(human_readable_error)
            # For failures, there are two callbacks: one for the controller
            # that failed, the second for the specific failure that occurred.
            failed_callback(controller)
            failure_callback(response)
            if not ignore_errors:
                raise ClusterUnavailable(human_readable_error)
        else:
            success_callback(controller)
            yield response
    # Each remaining controller [value] in the `calls` dict has timed out.
    for controller in calls.values():
        timeout_callback(controller)
        logger.error(
            "Error while calling %s: RPC connection timed out to rack "
            "controller '%s' (%s).",
            command_name,
            controller.hostname,
            controller.system_id,
        )


def get_error_message_for_exception(exception):
    """Return an error message for an exception.

    If `exception` is a NoConnectionsAvailable error,
    get_error_message_for_exception() will check to see if there's a
    UUID listed. If so, this is an error referring to a cluster.
    get_error_message_for_exception() will return an error message
    containing the cluster's name (as opposed to its UUID), which is
    more useful to users.

    If the exception has a message attached, return that. If not, create
    meaningful error message for the exception and return that instead.
    """
    # If we've gt a NoConnectionsAvailable error, check it for a UUID
    # field. If it's got one, we can report the cluster details more
    # helpfully.
    is_no_connections_error = isinstance(exception, NoConnectionsAvailable)
    has_uuid_field = getattr(exception, "uuid", None) is not None
    if is_no_connections_error and has_uuid_field:
        controller = RackController.objects.get(system_id=exception.uuid)
        return (
            "Unable to connect to rack controller '%s' (%s); no connections "
            "available." % (controller.hostname, controller.system_id)
        )
    elif isinstance(exception, ValidationError):
        error_message = " ".join(exception.messages)
    else:
        error_message = str(exception)

    if len(error_message) == 0:
        error_message = (
            "Unexpected exception: %s. See /var/log/maas/regiond.log "
            "on the region server for more information."
            % exception.__class__.__name__
        )
    return error_message
