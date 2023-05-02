# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RootKey model."""


from django.db.models import DateTimeField

from maasserver.models.timestampedmodel import TimestampedModel


class RootKey(TimestampedModel):
    """A root key for signing macaroons."""

    expiration = DateTimeField()
