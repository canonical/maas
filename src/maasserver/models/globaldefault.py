# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Global default objects."""


from django.db.models import AutoField, ForeignKey, Manager, PROTECT
from django.utils import timezone

from maasserver.enum import ALLOCATED_NODE_STATUSES, NODE_STATUS
from maasserver.models.cleansave import CleanSave
from maasserver.models.domain import Domain
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("default")


class GlobalDefaultManager(Manager):
    def instance(self):
        now = timezone.now()
        instance, _ = self.get_or_create(
            id=0,
            defaults=dict(
                id=0,
                domain=Domain.objects.get_or_create_default_domain(),
                created=now,
                updated=now,
            ),
        )
        return instance


class GlobalDefault(CleanSave, TimestampedModel):
    """Represents global default objects in MAAS."""

    objects = GlobalDefaultManager()

    # explicitly define the AutoField since default is BigAutoField and causing
    # modifications causes django to include this in the migration and not
    # allowing 0 as a value
    id = AutoField(primary_key=True, auto_created=True, verbose_name="ID")

    domain = ForeignKey(
        Domain, null=False, blank=False, editable=True, on_delete=PROTECT
    )

    def save(self, *args, **kwargs):
        previous_domain_id = (
            GlobalDefault.objects.filter(id=self.id)
            .values_list("domain_id", flat=True)
            .first()
        )
        if previous_domain_id not in (None, self.domain_id):
            from maasserver.models import Node

            # Don't change the domain for allocated nodes, or nodes booted
            # into an ephemeral environment for commissioning, testing, or
            # rescue (since DNS changes in the middle of these could impact
            # operation).
            status_change_exceptions = ALLOCATED_NODE_STATUSES | {
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.TESTING,
                NODE_STATUS.RESCUE_MODE,
            }
            unallocated_nodes = Node.objects.exclude(
                status__in=status_change_exceptions
            )
            unallocated_nodes.filter(domain_id=previous_domain_id).update(
                domain=self.domain
            )
        return super().save(*args, **kwargs)
