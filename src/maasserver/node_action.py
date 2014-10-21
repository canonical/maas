# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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
from textwrap import dedent

from crochet import TimeoutError
from django.core.urlresolvers import reverse
from maasserver import locks
from maasserver.enum import (
    NODE_BOOT,
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    )
from maasserver.exceptions import (
    NodeActionError,
    Redirect,
    StaticIPAddressExhaustion,
    )
from maasserver.models import (
    Node,
    SSHKey,
    )
from maasserver.node_status import is_failed_status
from provisioningserver.rpc.exceptions import (
    MultipleFailures,
    NoConnectionsAvailable,
    PowerActionAlreadyInProgress,
    )
from provisioningserver.utils.enum import map_enum

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

    display_bulk = abstractproperty("""
        Action name (bulk action).

        Will be used as the label for the action's name in bulk action
        dropdowns.
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

    def __init__(self, node, user, request=None):
        """Initialize a node action.

        All node actions' initializers must accept these same arguments,
        without variations.
        """
        self.node = node
        self.user = user
        self.request = request

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
    def execute(self, allow_redirect=True):
        """Perform this action.

        Even though this is not the API, the action may raise
        :class:`MAASAPIException` exceptions.  When this happens, the view
        will return to the client an http response reflecting the exception.

        :param allow_redirect: Whether a redirect (typically to a confirmation
            page) is possible.
        :return: A human-readable message confirming that the action has been
            performed.  It will be shown as an informational notice on the
            Node page.
        """

    def is_permitted(self):
        """Does the current user have the permission required?"""
        return self.user.has_perm(self.permission, self.node)

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
    display = "Delete node"
    display_bulk = "Delete selected nodes"
    actionable_statuses = ALL_STATUSES
    permission = NODE_PERMISSION.ADMIN

    def inhibit(self):
        if self.node.status == NODE_STATUS.ALLOCATED:
            return "You cannot delete this node because it's in use."
        return None

    def execute(self, allow_redirect=True):
        """Redirect to the delete view's confirmation page.

        The rest of deletion is handled by a specialized deletion view.
        All that the action really does is get you to its are-you-sure
        page.
        """
        if allow_redirect:
            raise Redirect(reverse('node-delete', args=[self.node.system_id]))
        else:
            self.node.delete()


class Commission(NodeAction):
    """Accept a node into the MAAS, and start the commissioning process."""
    name = "commission"
    display = "Commission node"
    display_bulk = "Commission selected nodes"
    actionable_statuses = (
        NODE_STATUS.NEW, NODE_STATUS.FAILED_COMMISSIONING, NODE_STATUS.READY,
        NODE_STATUS.BROKEN)
    permission = NODE_PERMISSION.ADMIN

    def execute(self, allow_redirect=True):
        """See `NodeAction.execute`."""
        try:
            self.node.start_commissioning(self.user)
        except RPC_EXCEPTIONS as exception:
            raise NodeActionError(exception)
        else:
            return "Node commissioning started."


class AbortCommissioning(NodeAction):
    """Abort the commissioning process."""
    name = "abort commissioning"
    display = "Abort commissioning"
    display_bulk = "Abort commissioning"
    actionable_statuses = (
        NODE_STATUS.COMMISSIONING,)
    permission = NODE_PERMISSION.ADMIN

    def execute(self, allow_redirect=True):
        """See `NodeAction.execute`."""
        try:
            self.node.abort_commissioning(self.user)
        except RPC_EXCEPTIONS as exception:
            raise NodeActionError(exception)
        else:
            return "Node commissioning aborted."


class AbortOperation(NodeAction):
    """Abort the current operation."""
    name = "abort operation"
    display = "Abort disk erasure"
    display_bulk = "Abort disk erasure"
    actionable_statuses = (
        NODE_STATUS.DISK_ERASING,)
    permission = NODE_PERMISSION.EDIT

    def execute(self, allow_redirect=True):
        """See `NodeAction.execute`."""
        try:
            self.node.abort_operation(self.user)
        except RPC_EXCEPTIONS as exception:
            raise NodeActionError(exception)
        else:
            return "Node operation aborted."


class UseCurtin(NodeAction):
    """Set this node to use curtin for installation."""
    name = "usecurtin"
    display = "Use the fast installer"
    display_bulk = "Mark nodes as using the fast installer"
    actionable_statuses = map_enum(NODE_STATUS).values()
    permission = NODE_PERMISSION.EDIT

    def is_permitted(self):
        permitted = super(UseCurtin, self).is_permitted()
        return permitted and self.node.boot_type == NODE_BOOT.DEBIAN

    def execute(self, allow_redirect=True):
        """See `NodeAction.execute`."""
        self.node.boot_type = NODE_BOOT.FASTPATH
        self.node.save()
        return "Node marked as using curtin for install."


class UseDI(NodeAction):
    """Set this node to use d-i for installation."""
    name = "usedi"
    display = "Use the Debian installer"
    display_bulk = "Mark nodes as using the Debian installer"
    actionable_statuses = map_enum(NODE_STATUS).values()
    permission = NODE_PERMISSION.EDIT

    def is_permitted(self):
        permitted = super(UseDI, self).is_permitted()
        return permitted and self.node.boot_type == NODE_BOOT.FASTPATH

    def execute(self, allow_redirect=True):
        """See `NodeAction.execute`."""
        self.node.boot_type = NODE_BOOT.DEBIAN
        self.node.save()
        return "Node marked as using the Debian installer."


class AcquireNode(NodeAction):
    """Acquire a node."""
    name = "acquire"
    display = "Acquire node"
    display_bulk = "Acquire selected nodes"
    actionable_statuses = (NODE_STATUS.READY, )
    permission = NODE_PERMISSION.VIEW

    def execute(self, allow_redirect=True):
        """See `NodeAction.execute`."""
        # The UI does not use OAuth, so there is no token to pass to the
        # acquire() call.

        with locks.node_acquire:
            self.node.acquire(self.user, token=None)

        return "This node is now allocated to you."


class StartNode(NodeAction):
    """Start a node."""
    name = "start"
    display_bulk = "Start selected nodes"
    actionable_statuses = (
        NODE_STATUS.READY, NODE_STATUS.ALLOCATED, NODE_STATUS.DEPLOYED)
    permission = NODE_PERMISSION.EDIT

    @property
    def display(self):
        # We explictly check for owner is None here, rather than owner
        # != self.user, because in practice the only people who are
        # going to see this button other than the node's owner are
        # administrators (because once once the node's owned, you need
        # EDIT permission to see this button).
        # We can safely assume that if you're seeing this and you don't
        # own the node, you're an admin, so you can still start it even
        # though you don't own it.
        if self.node.status == NODE_STATUS.READY and self.node.owner is None:
            label = "Acquire and start node"
        else:
            label = "Start node"
        return label

    def inhibit(self):
        """The user must have an SSH key, so that they access the node."""
        if not SSHKey.objects.get_keys_for_user(self.user).exists():
            return dedent("""\
                You have no means of accessing the node after starting it.
                Register an SSH key first.  Do this on your Preferences
                screen: click on the menu with your name at the top of the
                page, select Preferences, and look for the "SSH keys" section.
                """)
        return None

    def execute(self, allow_redirect=True):
        """See `NodeAction.execute`."""
        if self.node.owner is None:
            self.node.acquire(self.user, token=None)

        try:
            self.node.start(self.user)
        except StaticIPAddressExhaustion:
            raise NodeActionError(
                "%s: Failed to start, static IP addresses are exhausted."
                % self.node.hostname)
        except RPC_EXCEPTIONS as exception:
            raise NodeActionError(exception)
        else:
            return "This node has been asked to start up."


FAILED_STATUSES = [
    status for status in map_enum(NODE_STATUS).values()
    if is_failed_status(status)
]


class StopNode(NodeAction):
    """Stop a node."""
    name = "stop"
    display = "Stop node"
    display_bulk = "Stop selected nodes"
    actionable_statuses = (
        [NODE_STATUS.DEPLOYED] +
        # Also let a user ask a failed node to shutdown: this
        # is useful to try to recover from power failures.
        FAILED_STATUSES
    )
    permission = NODE_PERMISSION.EDIT

    def execute(self, allow_redirect=True):
        """See `NodeAction.execute`."""
        try:
            Node.objects.stop_nodes([self.node.system_id], self.user)
        except RPC_EXCEPTIONS as exception:
            raise NodeActionError(exception)
        else:
            return "This node has been asked to shut down."


class ReleaseNode(NodeAction):
    """Release a node."""
    name = "release"
    display = "Release node"
    display_bulk = "Release selected nodes"
    actionable_statuses = (
        NODE_STATUS.ALLOCATED, NODE_STATUS.DEPLOYED,
        NODE_STATUS.DEPLOYING, NODE_STATUS.FAILED_DEPLOYMENT,
        NODE_STATUS.FAILED_RELEASING,
        NODE_STATUS.FAILED_DISK_ERASING)
    permission = NODE_PERMISSION.EDIT

    def execute(self, allow_redirect=True):
        """See `NodeAction.execute`."""
        try:
            self.node.release_or_erase()
        except RPC_EXCEPTIONS as exception:
            raise NodeActionError(exception)
        else:
            return "This node is no longer allocated to you."


class MarkBroken(NodeAction):
    """Mark a node as 'broken'."""
    name = "mark-broken"
    display = "Mark node as broken"
    display_bulk = "Mark selected nodes as broken"
    actionable_statuses = [
        NODE_STATUS.NEW, NODE_STATUS.COMMISSIONING,
        NODE_STATUS.ALLOCATED, NODE_STATUS.RELEASING,
        NODE_STATUS.DEPLOYING] + FAILED_STATUSES
    permission = NODE_PERMISSION.EDIT

    def execute(self, allow_redirect=True):
        """See `NodeAction.execute`."""
        self.node.mark_broken(
            "Manually marked as broken by user '%s'" % self.user.username)
        return "Node marked broken."


class MarkFixed(NodeAction):
    """Mark a broken node as fixed and set its state to 'READY'."""
    name = "mark-fixed"
    display = "Mark node as fixed"
    display_bulk = "Mark selected nodes as fixed"
    actionable_statuses = (NODE_STATUS.BROKEN, )
    permission = NODE_PERMISSION.ADMIN

    def execute(self, allow_redirect=True):
        """See `NodeAction.execute`."""
        self.node.mark_fixed()
        return "Node marked fixed."


ACTION_CLASSES = (
    # Status-changing actions.
    AcquireNode,
    Commission,
    ReleaseNode,
    AbortCommissioning,
    AbortOperation,
    MarkBroken,
    MarkFixed,
    Delete,
    # Start / stop actions.
    StartNode,
    StopNode,
    # Config change actions.
    UseCurtin,
    UseDI,
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
    applicable_actions = (
        action_class(node, user, request)
        for action_class in classes
        if node.status in action_class.actionable_statuses)
    return OrderedDict(
        (action.name, action)
        for action in applicable_actions
        if action.is_permitted())
