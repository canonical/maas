# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Node actions.

These are actions that appear as buttons on the UI's Node page, depending
on the node's state, the user's privileges etc.

To define a new node action, derive a class for it from :class:`NodeAction`,
provide the missing pieces documented in the class, and add it to
`ACTION_CLASSES`.  The actions will always appear on the page in the same
order as they do in `ACTION_CLASSES`.
"""

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
from maasserver.clusterrpc.boot_images import RackControllersImporter
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
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
from maasserver.preseed import get_curtin_config
from maasserver.utils.orm import post_commit_do
from maasserver.utils.osystems import (
    validate_hwe_kernel,
    validate_osystem_and_distro_series,
)
from metadataserver.enum import SCRIPT_STATUS
from provisioningserver.rpc.exceptions import (
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
    NoConnectionsAvailable,
    PowerActionAlreadyInProgress,
    TimeoutError,
)


class NodeAction(metaclass=ABCMeta):
    """Base class for node actions."""

    name = abstractproperty("""
        Action name.

        Will be used as the name for the action in all the forms.
        """)

    display = abstractproperty("""
        Action name.

        Will be used as the label for the action's button.
        """)

    for_type = abstractproperty("""
        Can only be performed when the node type is in the for_type set.

        A list of NODE_TYPEs which are applicable for this action.
        """)

    # Optional node states for which this action makes sense.
    # A collection of NODE_STATUS values.  The action will be available
    # only if `node.status in action.actionable_statuses`.
    actionable_statuses = None

    permission = abstractproperty("""
        Required permission.

        A NODE_PERMISSION value.  The action will be available only if the
        user has this given permission on the subject node.
        """)

    # Optional node permission that will be used when the action
    # is being applied to a node_type which is node
    node_permission = None

    # Whether the action is allowed when the node is locked
    allowed_when_locked = False

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

        If the node is not node_type node then actionable_statuses will not
        be used, as the status doesn't matter for a non-node type.
        """
        if self.node.node_type not in self.for_type:
            return False
        elif (self.node_permission == NODE_PERMISSION.ADMIN and
                not self.user.is_superuser):
            return False
        elif self.node.locked and not self.allowed_when_locked:
            return False
        elif self.node.node_type == NODE_TYPE.MACHINE:
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
        """Return the permission value depending on if the node_type."""
        if(self.node.node_type == NODE_TYPE.MACHINE and
           self.node_permission is not None):
            return self.node_permission
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
    node_permission = NODE_PERMISSION.ADMIN
    for_type = {i for i, _ in enumerate(NODE_TYPE_CHOICES)}

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
    node_permission = NODE_PERMISSION.ADMIN
    for_type = {i for i, _ in enumerate(NODE_TYPE_CHOICES)}

    def execute(self, zone_id=None):
        """See `NodeAction.execute`."""
        zone = Zone.objects.get(id=zone_id)
        self.node.set_zone(zone)


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
    for_type = {NODE_TYPE.MACHINE}

    def execute(
            self, enable_ssh=False, skip_networking=False,
            skip_storage=False, commissioning_scripts=[],
            testing_scripts=[]):
        """See `NodeAction.execute`."""
        try:
            self.node.start_commissioning(
                self.user,
                enable_ssh=enable_ssh,
                skip_networking=skip_networking,
                skip_storage=skip_storage,
                commissioning_scripts=commissioning_scripts,
                testing_scripts=testing_scripts)
        except RPC_EXCEPTIONS + (ExternalProcessError, ValidationError) as e:
            raise NodeActionError(e)


class Test(NodeAction):
    """Start testing a node."""
    name = "test"
    display = "Test hardware"
    display_sentence = "tested"
    actionable_statuses = (
        NODE_STATUS.FAILED_COMMISSIONING,
        NODE_STATUS.READY,
        NODE_STATUS.RESERVED,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.FAILED_DEPLOYMENT,
        NODE_STATUS.DEPLOYED,
        NODE_STATUS.MISSING,
        NODE_STATUS.RETIRED,
        NODE_STATUS.BROKEN,
        NODE_STATUS.RESCUE_MODE,
        NODE_STATUS.FAILED_RELEASING,
        NODE_STATUS.FAILED_DISK_ERASING,
        NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
        NODE_STATUS.FAILED_EXITING_RESCUE_MODE,
        NODE_STATUS.FAILED_TESTING,
    )
    permission = NODE_PERMISSION.VIEW
    for_type = {NODE_TYPE.MACHINE, NODE_TYPE.RACK_CONTROLLER}

    def execute(self, enable_ssh=False, testing_scripts=[]):
        try:
            self.node.start_testing(
                self.user, enable_ssh=enable_ssh,
                testing_scripts=testing_scripts)
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
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.TESTING,
    )
    permission = NODE_PERMISSION.ADMIN
    for_type = {NODE_TYPE.MACHINE}

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
    for_type = {NODE_TYPE.MACHINE}

    def execute(self):
        """See `NodeAction.execute`."""
        with locks.node_acquire:
            try:
                self.node.acquire(self.user, token=None)
            except ValidationError as e:
                raise NodeActionError(e)


class Deploy(NodeAction):
    """Deploy a node."""
    name = "deploy"
    display = "Deploy"
    display_sentence = "deployed"
    actionable_statuses = (NODE_STATUS.READY, NODE_STATUS.ALLOCATED)
    permission = NODE_PERMISSION.VIEW
    for_type = {NODE_TYPE.MACHINE}

    def execute(self, osystem=None, distro_series=None, hwe_kernel=None):
        """See `NodeAction.execute`."""
        if self.node.owner is None:
            with locks.node_acquire:
                try:
                    self.node.acquire(self.user, token=None)
                except ValidationError as e:
                    raise NodeActionError(e)

        if osystem and distro_series:
            try:
                self.node.osystem, self.node.distro_series = (
                    validate_osystem_and_distro_series(osystem, distro_series))
                self.node.save()
            except ValidationError as e:
                raise NodeActionError(e)

        try:
            self.node.hwe_kernel = validate_hwe_kernel(
                hwe_kernel, self.node.min_hwe_kernel,
                self.node.architecture, self.node.osystem,
                self.node.distro_series)
            self.node.save()
        except ValidationError as e:
            raise NodeActionError(e)

        try:
            get_curtin_config(self.node)
        except Exception as e:
            raise NodeActionError(
                "Failed to retrieve curtin config: %s" % e)

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
    for_type = {NODE_TYPE.MACHINE, NODE_TYPE.RACK_CONTROLLER}

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
    for_type = {NODE_TYPE.MACHINE, NODE_TYPE.RACK_CONTROLLER}

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
    for_type = {NODE_TYPE.MACHINE}

    def execute(self, erase=False, secure_erase=False, quick_erase=False):
        """See `NodeAction.execute`."""
        try:
            self.node.release_or_erase(
                self.user, erase=erase,
                secure_erase=secure_erase, quick_erase=quick_erase)
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
        NODE_STATUS.TESTING,
    ] + FAILED_STATUSES
    permission = NODE_PERMISSION.EDIT
    for_type = {NODE_TYPE.MACHINE}

    def execute(self):
        """See `NodeAction.execute`."""
        self.node.mark_broken(self.user, "via web interface")


class MarkFixed(NodeAction):
    """Mark a broken node as fixed and set its state to 'READY'."""
    name = "mark-fixed"
    display = "Mark fixed"
    display_sentence = "marked fixed"
    actionable_statuses = (NODE_STATUS.BROKEN, )
    permission = NODE_PERMISSION.ADMIN
    for_type = {NODE_TYPE.MACHINE}

    def execute(self):
        """See `NodeAction.execute`."""
        if self.node.power_state == POWER_STATE.ON:
            raise NodeActionError(
                "Unable to be mark fixed because the power is currently on.")
        if not self.has_commissioning_data():
            raise NodeActionError(
                "Unable to be mark fixed because it has not been commissioned "
                "successfully.")
        self.node.mark_fixed(self.user)

    def has_commissioning_data(self):
        """Return False when the node is missing the required commissioning
        data."""
        script_set = self.node.current_commissioning_script_set
        if script_set is None:
            return False
        else:
            script_failures = script_set.scriptresult_set.exclude(
                status=SCRIPT_STATUS.PASSED)
            return not script_failures.exists()


class Lock(NodeAction):
    """Lock a node."""

    name = "lock"
    display = "Lock"
    display_sentence = "Lock"
    actionable_statuses = (NODE_STATUS.DEPLOYED,)
    permission = NODE_PERMISSION.LOCK
    for_type = {NODE_TYPE.MACHINE}

    def execute(self):
        self.node.lock(self.user, "via web interface")


class Unlock(NodeAction):
    """Unlock a node."""

    name = "unlock"
    display = "Unlock"
    display_sentence = "Unlock"
    actionable_statuses = ALL_STATUSES
    permission = NODE_PERMISSION.LOCK
    for_type = {NODE_TYPE.MACHINE}
    allowed_when_locked = True

    def is_actionable(self):
        if not super().is_actionable():
            return False
        # don't show action if not locked
        return self.node.locked

    def execute(self):
        self.node.unlock(self.user, "via web interface")


class OverrideFailedTesting(NodeAction):
    """Override failed tests and reset node into a usable state."""
    name = "override-failed-testing"
    display = "Override failed testing"
    display_sentence = "Override failed testing"
    actionable_statuses = (NODE_STATUS.FAILED_TESTING, )
    permission = NODE_PERMISSION.VIEW
    for_type = {NODE_TYPE.MACHINE, NODE_TYPE.RACK_CONTROLLER}

    def execute(self):
        """See `NodeAction.execute`."""
        self.node.override_failed_testing(self.user, "via web interface")


class ImportImages(NodeAction):
    """Import images on a rack or region and rack controller."""
    name = "import-images"
    display = "Import Images"
    display_sentence = "importing images"
    permission = NODE_PERMISSION.ADMIN
    for_type = {
        NODE_TYPE.RACK_CONTROLLER,
        NODE_TYPE.REGION_AND_RACK_CONTROLLER
    }

    def execute(self):
        """See `NodeAction.execute`."""
        try:
            post_commit_do(
                RackControllersImporter.schedule, self.node.system_id)
        except RPC_EXCEPTIONS as exception:
            raise NodeActionError(exception)


class RescueMode(NodeAction):
    """Start the rescue mode process."""
    name = "rescue-mode"
    display = "Rescue mode"
    display_sentence = "rescue mode"
    actionable_statuses = (
        NODE_STATUS.NEW,
        NODE_STATUS.FAILED_COMMISSIONING,
        NODE_STATUS.READY,
        NODE_STATUS.RESERVED,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.FAILED_DEPLOYMENT,
        NODE_STATUS.DEPLOYED,
        NODE_STATUS.MISSING,
        NODE_STATUS.RETIRED,
        NODE_STATUS.BROKEN,
        NODE_STATUS.FAILED_DISK_ERASING,
        NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
        NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
        NODE_STATUS.FAILED_EXITING_RESCUE_MODE,
        NODE_STATUS.FAILED_TESTING,
    )
    permission = NODE_PERMISSION.ADMIN
    for_type = {NODE_TYPE.MACHINE}

    def execute(self):
        """See `NodeAction.execute`."""
        try:
            self.node.start_rescue_mode(self.user)
        except RPC_EXCEPTIONS + (ExternalProcessError,) as exception:
            raise NodeActionError(exception)


class ExitRescueMode(NodeAction):
    """Exit the rescue mode process."""
    name = "exit-rescue-mode"
    display = "Exit rescue mode"
    display_sentence = "exit rescue mode"
    actionable_statuses = (
        NODE_STATUS.RESCUE_MODE,
        NODE_STATUS.ENTERING_RESCUE_MODE,
        NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
        NODE_STATUS.FAILED_EXITING_RESCUE_MODE,
    )
    permission = NODE_PERMISSION.ADMIN
    for_type = {NODE_TYPE.MACHINE}

    def execute(self):
        """See `NodeAction.execute`."""
        try:
            self.node.stop_rescue_mode(self.user)
        except RPC_EXCEPTIONS + (ExternalProcessError,) as exception:
            raise NodeActionError(exception)


ACTION_CLASSES = (
    Commission,
    Acquire,
    Deploy,
    PowerOn,
    PowerOff,
    Release,
    Abort,
    Test,
    RescueMode,
    ExitRescueMode,
    MarkBroken,
    MarkFixed,
    OverrideFailedTesting,
    Lock,
    Unlock,
    SetZone,
    ImportImages,
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
