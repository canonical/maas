from django.db.models import JSONField, TextField

from maasserver.models.timestampedmodel import TimestampedModel


class Secret(TimestampedModel):
    """A secret used by other models or MAAS itself.

    These are collected in a single model and addressed via a path that matches
    the one used when Vault integration is enabled.
    """

    path = TextField(primary_key=True)
    value = JSONField()
