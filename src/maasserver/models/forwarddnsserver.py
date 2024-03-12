""" Forward DNS Server Objects."""

__all__ = [
    "ForwardDNSServerManager",
    "ForwardDNSServer",
]


from django.db.models import (
    GenericIPAddressField,
    IntegerField,
    Manager,
    ManyToManyField,
)

from maasserver.models.cleansave import CleanSave
from maasserver.models.domain import Domain
from maasserver.models.timestampedmodel import TimestampedModel


class ForwardDNSServerManager(Manager):
    pass


# Due to migration 0155 calling Domain's manager directly, we cannot add forward dns servers as a column to a Domain
# so a separate table where one or more ForwardDNSServer(s) can be used in many Domains.
class ForwardDNSServer(CleanSave, TimestampedModel):
    """A `ForwardDNSServer`.
    :ivar ip_address: The IP address of the forward DNS server to forward queries to.
    :ivar domains: A many to many reference to domains that forward to this server."""

    objects = ForwardDNSServerManager()

    ip_address = GenericIPAddressField(
        null=False, default=None, editable=False, unique=True
    )

    port = IntegerField(null=False, default=53)

    domains = ManyToManyField(Domain)

    @property
    def ip_and_port(self):
        return f"{self.ip_address}:{self.port}"
