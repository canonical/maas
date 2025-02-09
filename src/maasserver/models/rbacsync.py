# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RBACSync objects."""

from django.db.models import Manager, Model
from django.db.models.fields import CharField, DateTimeField, IntegerField

from provisioningserver.enum import enum_choices


class RBAC_ACTION:
    # Perform a full sync.
    FULL = "full"
    # Add a new resource.
    ADD = "add"
    # Update a resource.
    UPDATE = "update"
    # Remove a resource.
    REMOVE = "remove"


RBAC_ACTION_CHOICES = enum_choices(RBAC_ACTION)


class RBACSyncManager(Manager):
    """Manager for `RBACSync` records."""

    def changes(self, resource_type):
        """Returns the changes that have occurred for `resource_type`."""
        return list(
            self.filter(resource_type__in=["", resource_type]).order_by("id")
        )

    def clear(self, resource_type):
        """Deletes all `RBACSync` for `resource_type`."""
        self.filter(resource_type__in=["", resource_type]).delete()


class RBACSync(Model):
    """A row in this table denotes a change that requires information RBAC
    micro-service to be updated.

    Typically this will be populated by a trigger within the database. A
    listeners in regiond will be notified and consult the un-synced records
    in this table. This way we can consistently publish RBAC information to the
    RBAC service in an HA environment.
    """

    objects = RBACSyncManager()

    action = CharField(
        editable=False,
        max_length=6,
        null=False,
        blank=True,
        choices=RBAC_ACTION_CHOICES,
        default=RBAC_ACTION.FULL,
        help_text="Action that should occur on the RBAC service.",
    )

    # An '' string is used when action is 'full'.
    resource_type = CharField(
        editable=False,
        max_length=255,
        null=False,
        blank=True,
        help_text="Resource type that as been added/updated/removed.",
    )

    # A `None` is used when action is 'full'.
    resource_id = IntegerField(
        editable=False,
        null=True,
        blank=True,
        help_text="Resource ID that has been added/updated/removed.",
    )

    # A '' string is used when action is 'full'.
    resource_name = CharField(
        editable=False,
        max_length=255,
        null=False,
        blank=True,
        help_text="Resource name that has been added/updated/removed.",
    )

    # This field is informational.
    created = DateTimeField(
        editable=False, null=False, auto_now=False, auto_now_add=True
    )

    # This field is informational.
    source = CharField(
        editable=False,
        max_length=255,
        null=False,
        blank=True,
        help_text="A brief explanation what changed.",
    )


class RBACLastSync(Model):
    """ID returned after the last synchronization for each resource type."""

    resource_type = CharField(
        editable=False,
        max_length=255,
        null=False,
        blank=False,
        unique=True,
        help_text="Resource type that as been sync'd.",
    )
    sync_id = CharField(
        editable=False,
        max_length=255,
        null=False,
        blank=False,
        help_text="ID returned by the RBAC service after the last sync.",
    )
