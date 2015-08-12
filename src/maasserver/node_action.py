# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Node actions.

These are actions that appear as buttons on the UI's Node page, depending
on the node's state, the user's privileges etc.

To define a new node action, derive a class for it from :class:`NodeAction`,
provide the missing pieces documented in the class, and add it to
`ACTION_CLASSES`.  The actions will always appear on the page in the same
order as they do in `ACTION_CLASSES`.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    'compile_node_actions',
]

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
)
from collections import OrderedDict

from crochet import TimeoutError
from django.core.exceptions import ValidationError
from maasserver import locks
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    POWER_STATE,
)
from maasserver.exceptions import (
    NodeActionError,
    StaticIPAddressExhaustion,
)
from maasserver.models import Zone
from maasserver.node_status import (
    is_failed_status,
    NON_MONITORED_STATUSES,
)
from maasserver.utils.osystems import validate_hwe_kernel
from metadataserver.enum import RESULT_TYPE
from metadataserver.models.noderesult import NodeResult
from provisioningserver.rpc.exceptions import (
    MultipleFailures,
    NoConnectionsAvailable,
    PowerActionAlreadyInProgress,
)
from provisioningserver.utils.enum import map_enum
from provisioningserver.utils.shell import ExternalProcessError

# All node statuses.
ALL_STATUSES = set(NODE_STATUS_CHOICES_DICT.keys())


# A collection of errors that may be raised by RPC-based actions that
# should be converted to NodeActionErrors.
RPC_EXCEPTIONS = (
    MultipleFailures,
    NoConnectionsAvailable,
    PowerActionAlreadyInProgress,
    TimeoutError,
)


class NodeAction:
    """Base class for node actions."""

    __metaclass__ = ABCMeta

    name = abstractproperty("""
        Action name.

        Will be used as the name for the action in all the forms.
        """)

    display = abstractproperty("""
        Action name.

        Will be used as the label for the action's button.
        """)

    installable_only = abstractproperty("""
        Can only be performed on a installable node.

        A boolean value.  True for only available for installable node, false
        otherwise.
        """)

    actionable_statuses = abstractproperty("""
        Node states for which this action makes sense.

        A collection of NODE_STATUS values.  The action will be available
        only if `node.status in action.actionable_statuses`.
        """)

    permission = abstractproperty("""
        Required permission.

        A NODE_PERMISSION value.  The action will be available only if the
        user has this given permission on the subject node.
        """)

    # Optional installable permission that will be used when the action
    # is being applied to a node that is installable.
    installable_permission = None

    def __init__(self, node, user, request=None):
        """Initialize a node action.

        All node actions' initializers must accept these same arguments,
        without variations.
        """
        self.node = node
        self.user = user
        self.request = request

    def is_actionable(self):
        """Can this action be performed?

        If the node is not installable then actionable_statuses will not
        be used, as the status doesn't matter for an uninstallable node.
        """
        if self.installable_only and not self.node.installable:
            return False
        if self.node.installable:
            return self.node.status in self.actionable_statuses
        return True

    def inhibit(self):
        """Overridable: is there any reason not to offer this action?

        This property may return a reason to inhibit this action, in which
        case its button may still be visible in the UI, but disabled.  A
        tooltip will provide the reason, as returned by this method.

        :return: A human-readable reason to inhibit the action, or None if
            the action is valid.
        """
        return None

    @abstractmethod
    def execute(self):
        """Perform this action.

        Even though this is not the API, the action may raise
        :class:`MAASAPIException` exceptions.  When this happens, the view
        will return to the client an http response reflecting the exception.
        """

    def get_permission(self):
        """Return the permission value depending on if the node is
        installable or not."""
        if self.node.installable and self.installable_permission is not None:
            return self.installable_permission
        return self.permission

    def is_permitted(self):
        """Does the current user have the permission required?"""
        return self.user.has_perm(self.get_permission(), self.node)

    # Uninitialized inhibititions cache.
    _cached_inhibition = object()

    @property
    def inhibition(self):
        """Caching version of `inhibit`."""
        if self._cached_inhibition == NodeAction._cached_inhibition:
            self._cached_inhibition = self.inhibit()
        return self._cached_inhibition


class Delete(NodeAction):
    """Delete a node."""
    name = "delete"
    display = "Delete"
    display_sentence = "deleted"
    actionable_statuses = ALL_STATUSES
    permission = NODE_PERMISSION.EDIT
    installable_permission = NODE_PERMISSION.ADMIN
    installable_only = False

    def execute(self):
        """Redirect to the delete view's confirmation page.

        The rest of deletion is handled by a specialized deletion view.
        All that the action really does is get you to its are-you-sure
        page.
        """
        self.node.delete()


class SetZone(NodeAction):
    """Set the zone of a node."""
    name = "set-zone"
    display = "Set Zone"
    display_sentence = "Zone set"
    actionable_statuses = ALL_STATUSES
    permission = NODE_PERMISSION.EDIT
    installable_permission = NODE_PERMISSION.ADMIN
    installable_only = False

    def execute(self, zone_id=None):
        """See `NodeAction.execute`."""
        zone = Zone.objects.get(id=zone_id)
        self.node.set_zone(zone)

    def is_actionable(self):
        """Returns true if the selected nodes can be added to a zone"""
        return super(SetZone, self).is_actionable()


class Commission(NodeAction):
    """Accept a node into the MAAS, and start the commissioning process."""
    name = "commission"
    display = "Commission"
    display_sentence = "commissioned"
    actionable_statuses = (
        NODE_STATUS.NEW,
        NODE_STATUS.FAILED_COMMISSIONING,
        NODE_STATUS.READY,
        NODE_STATUS.BROKEN,
    )
    permission = NODE_PERMISSION.ADMIN
    installable_only = True

    def execute(self):
        """See `NodeAction.execute`."""
        if self.node.power_state == POWER_STATE.ON:
            raise NodeActionError(
                "Unable to be commissioned because the power is currently on.")
        try:
            self.node.start_commissioning(self.user)
        except RPC_EXCEPTIONS + (ExternalProcessError,) as exception:
            raise NodeActionError(exception)


class Abort(NodeAction):
    """Abort the current operation."""
    name = "abort"
    display = "Abort"
    display_sentence = "aborted"
    actionable_statuses = (
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.DEPLOYING
    )
    permission = NODE_PERMISSION.ADMIN
    installable_only = True

    def execute(self):
        """See `NodeAction.execute`."""
        try:
            self.node.abort_operation(self.user)
        except RPC_EXCEPTIONS + (ExternalProcessError,) as exception:
            raise NodeActionError(exception)


class Acquire(NodeAction):
    """Acquire a node."""
    name = "acquire"
    display = "Acquire"
    display_sentence = "acquired"
    actionable_statuses = (NODE_STATUS.READY, )
    permission = NODE_PERMISSION.VIEW
    installable_only = True

    def execute(self):
        """See `NodeAction.execute`."""
        with locks.node_acquire:
            self.node.acquire(self.user, token=None)


class Deploy(NodeAction):
    """Deploy a node."""
    name = "deploy"
    display = "Deploy"
    display_sentence = "deployed"
    actionable_statuses = (NODE_STATUS.READY, NODE_STATUS.ALLOCATED)
    permission = NODE_PERMISSION.VIEW
    installable_only = True

    def execute(self, osystem=None, distro_series=None, hwe_kernel=None):
        """See `NodeAction.execute`."""
        if self.node.owner is None:
            with locks.node_acquire:
                self.node.acquire(self.user, token=None)

        # Set the osystem in distro_series if provided and not empty.
        if osystem and distro_series:
            self.node.osystem = osystem
            self.node.distro_series = distro_series
            self.node.save()

        try:
            self.node.hwe_kernel = validate_hwe_kernel(
                hwe_kernel, self.node.min_hwe_kernel,
                self.node.architecture, self.node.osystem,
                self.node.distro_series)
            self.node.save()
        except ValidationError as e:
            raise NodeActionError(e.message)

        try:
            self.node.start(self.user)
        except StaticIPAddressExhaustion:
            raise NodeActionError(
                "%s: Failed to start, static IP addresses are exhausted."
                % self.node.hostname)
        except RPC_EXCEPTIONS + (ExternalProcessError,) as exception:
            raise NodeActionError(exception)


class PowerOn(NodeAction):
    """Power on a node."""
    name = "on"
    display = "Power on"
    display_sentence = "powered on"
    actionable_statuses = (
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.DEPLOYED,
        NODE_STATUS.BROKEN,
    )
    permission = NODE_PERMISSION.EDIT
    installable_only = True

    def execute(self):
        """See `NodeAction.execute`."""
        try:
            self.node.start(self.user)
        except StaticIPAddressExhaustion:
            raise NodeActionError(
                "%s: Failed to start, static IP addresses are exhausted."
                % self.node.hostname)
        except RPC_EXCEPTIONS + (ExternalProcessError,) as exception:
            raise NodeActionError(exception)

    def is_actionable(self):
        is_actionable = super(PowerOn, self).is_actionable()
        return is_actionable


FAILED_STATUSES = [
    status for status in map_enum(NODE_STATUS).values()
    if is_failed_status(status)
]


class PowerOff(NodeAction):
    """Power off a node."""
    name = "off"
    display = "Power off"
    display_sentence = "powered off"
    # Let a user power off a node in any non-active status.
    actionable_statuses = NON_MONITORED_STATUSES
    permission = NODE_PERMISSION.EDIT
    installable_only = True

    def execute(self):
        """See `NodeAction.execute`."""
        try:
            self.node.stop(self.user)
        except RPC_EXCEPTIONS + (ExternalProcessError,) as exception:
            raise NodeActionError(exception)

    def is_actionable(self):
        is_actionable = super(PowerOff, self).is_actionable()
        return is_actionable and (
            self.node.power_state != POWER_STATE.OFF)


class Release(NodeAction):
    """Release a node."""
    name = "release"
    display = "Release"
    display_sentence = "released"
    actionable_statuses = (
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.DEPLOYED,
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.FAILED_DEPLOYMENT,
        NODE_STATUS.FAILED_RELEASING,
        NODE_STATUS.FAILED_DISK_ERASING,
    )
    permission = NODE_PERMISSION.EDIT
    installable_only = True

    def execute(self):
        """See `NodeAction.execute`."""
        try:
            self.node.release_or_erase()
            self.node.hwe_kernel = ""
            self.node.save()
        except RPC_EXCEPTIONS + (ExternalProcessError,) as exception:
            raise NodeActionError(exception)


class MarkBroken(NodeAction):
    """Mark a node as 'broken'."""
    name = "mark-broken"
    display = "Mark broken"
    display_sentence = "marked broken"
    actionable_statuses = [
        NODE_STATUS.NEW,
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.READY,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.RELEASING,
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.DEPLOYED,
        NODE_STATUS.DISK_ERASING,
    ] + FAILED_STATUSES
    permission = NODE_PERMISSION.EDIT
    installable_only = True

    def execute(self):
        """See `NodeAction.execute`."""
        self.node.mark_broken(
            "Manually marked as broken by user '%s'" % self.user.username)


class MarkFixed(NodeAction):
    """Mark a broken node as fixed and set its state to 'READY'."""
    name = "mark-fixed"
    display = "Mark fixed"
    display_sentence = "marked fixed"
    actionable_statuses = (NODE_STATUS.BROKEN, )
    permission = NODE_PERMISSION.ADMIN
    installable_only = True

    def execute(self):
        """See `NodeAction.execute`."""
        if self.node.power_state == POWER_STATE.ON:
            raise NodeActionError(
                "Unable to be mark fixed because the power is currently on.")
        if not self.has_commissioning_data():
            raise NodeActionError(
                "Unable to be mark fixed because it has not been commissioned "
                "successfully.")
        self.node.mark_fixed()

    def has_commissioning_data(self):
        """Return True when the node is missing the required commissioning
        data."""
        results = list(NodeResult.objects.filter(
            node=self.node, result_type=RESULT_TYPE.COMMISSIONING))
        if len(results) == 0:
            return False
        failed_results = [
            result
            for result in results
            if result.script_result != 0
        ]
        if len(failed_results) > 0:
            return False
        return True


ACTION_CLASSES = (
    Commission,
    Acquire,
    Deploy,
    PowerOn,
    PowerOff,
    Release,
    Abort,
    MarkBroken,
    MarkFixed,
    SetZone,
    Delete,
)

ACTIONS_DICT = OrderedDict((action.name, action) for action in ACTION_CLASSES)


def compile_node_actions(node, user, request=None, classes=ACTION_CLASSES):
    """Provide :class:`NodeAction` objects for given request.

    :param node: The :class:`Node` that the request pertains to.
    :param user: The :class:`User` making the request.
    :param request: The :class:`HttpRequest` being serviced.  It may be used
        to obtain information about the OAuth token being used.
    :return: An :class:`OrderedDict` mapping applicable actions' display names
        to corresponding :class:`NodeAction` instances.  The dict is ordered
        for consistent display.
    """
    actions = (
        action_class(node, user, request)
        for action_class in classes)
    applicable_actions = (
        action for action in actions
        if action.is_actionable())
    return OrderedDict(
        (action.name, action)
        for action in applicable_actions
        if action.is_permitted())
