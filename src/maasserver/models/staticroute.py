# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Static route between two subnets using a gateway."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import (
    CASCADE,
    ForeignKey,
    GenericIPAddressField,
    Manager,
    PositiveIntegerField,
)
from django.shortcuts import get_object_or_404

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class StaticRouteManager(Manager):
    def get_staticroute_or_404(self, staticroute_id, user, perm):
        """Fetch a `StaticRoute` by its id.  Raise exceptions if no
        `StaticRoute` with this id exist or if the provided user has not the
        required permission to access this `StaticRoute`.

        :param staticroute_id: The static route id.
        :type staticroute_id: integer
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :param perm: The permission to assert that the user has on the node.
        :type perm: unicode
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        route = get_object_or_404(self.model, id=staticroute_id)
        if user.has_perm(perm, route):
            return route
        else:
            raise PermissionDenied()


class StaticRoute(CleanSave, TimestampedModel):
    """Static route between two subnets using a gateway."""

    class Meta:
        unique_together = ("source", "destination", "gateway_ip")

    objects = StaticRouteManager()

    source = ForeignKey(
        "Subnet", blank=False, null=False, related_name="+", on_delete=CASCADE
    )

    destination = ForeignKey(
        "Subnet", blank=False, null=False, related_name="+", on_delete=CASCADE
    )

    gateway_ip = GenericIPAddressField(
        unique=False,
        null=False,
        blank=False,
        editable=True,
        verbose_name="Gateway IP",
    )

    metric = PositiveIntegerField(blank=False, null=False)

    def clean(self):
        if self.source_id is not None and self.destination_id is not None:
            if self.source == self.destination:
                raise ValidationError(
                    "source and destination cannot be the same subnet."
                )
            source_network = self.source.get_ipnetwork()
            source_version = source_network.version
            destination_version = self.destination.get_ipnetwork().version
            if source_version != destination_version:
                raise ValidationError(
                    "source and destination must be the same IP version."
                )
            if (
                self.gateway_ip is not None
                and self.gateway_ip not in source_network
            ):
                raise ValidationError(
                    "gateway_ip must be with in the source subnet."
                )
