# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Global default objects."""

__all__ = [
    "GlobalDefault",
    ]

from datetime import datetime

from django.db.models import (
    ForeignKey,
    Manager,
    PROTECT,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.domain import Domain
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("default")


class GlobalDefaultManager(Manager):

    def instance(self):
        now = datetime.now()
        instance, _ = self.get_or_create(
            id=0,
            defaults=dict(
                id=0,
                domain=Domain.objects.get_or_create_default_domain(),
                created=now,
                updated=now
            )
        )
        return instance


class GlobalDefault(CleanSave, TimestampedModel):
    """Represents global default objects in MAAS."""

    objects = GlobalDefaultManager()

    domain = ForeignKey(
        Domain, null=False, blank=False, editable=True, on_delete=PROTECT)
