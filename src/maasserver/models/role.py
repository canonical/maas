# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""User roles and permissions."""

from django.contrib.auth.models import User
from django.db.models import (
    CharField,
    ManyToManyField,
    Model,
    TextField,
)
from maasserver.fields import MODEL_NAME_VALIDATOR
from maasserver.models import ResourcePool


class Role(Model):
    """A role defines user access to resource pools."""

    name = CharField(
        max_length=255, unique=True, blank=False,
        validators=[MODEL_NAME_VALIDATOR])
    description = TextField(blank=True, editable=True)
    users = ManyToManyField(User)
    resource_pools = ManyToManyField(ResourcePool)
