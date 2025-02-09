# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a running service on regiond or rackd."""

from django.db.models import CASCADE, CharField, ForeignKey, Manager

from maasserver.enum import NODE_TYPE, SERVICE_STATUS, SERVICE_STATUS_CHOICES
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel

# Services that run on the region controller. NOTE that this needs to include
# services overseen by the region's ServiceMonitor.
REGION_SERVICES = frozenset(
    {
        "bind9",
        "ntp_region",
        "proxy",
        "regiond",
        "reverse_proxy",
        "syslog_region",
        "temporal",
        "temporal-worker",
    }
)

# Services that run on the rack controller. NOTE that this needs to include
# services overseen by the rack's ServiceMonitor.
RACK_SERVICES = frozenset(
    {
        "rackd",
        "tftp",
        "http",
        "dhcpd",
        "dhcpd6",
        "ntp_rack",
        "dns_rack",
        "proxy_rack",
        "syslog_rack",
        "agent",
    }
)

# Statuses that should be set on each service when node is marked dead. NOTE
# that this needs to include services overseen by the rack's ServiceMonitor.
DEAD_STATUSES = {
    "regiond": SERVICE_STATUS.DEAD,
    "bind9": SERVICE_STATUS.UNKNOWN,
    "proxy": SERVICE_STATUS.UNKNOWN,
    "rackd": SERVICE_STATUS.DEAD,
    "tftp": SERVICE_STATUS.DEAD,
    "dhcpd": SERVICE_STATUS.DEAD,
    "dhcpd6": SERVICE_STATUS.DEAD,
    "http": SERVICE_STATUS.UNKNOWN,
    "ntp_region": SERVICE_STATUS.UNKNOWN,
    "syslog_region": SERVICE_STATUS.UNKNOWN,
    "ntp_rack": SERVICE_STATUS.DEAD,
    "dns_rack": SERVICE_STATUS.UNKNOWN,
    "proxy_rack": SERVICE_STATUS.UNKNOWN,
    "syslog_rack": SERVICE_STATUS.UNKNOWN,
    "reverse_proxy": SERVICE_STATUS.UNKNOWN,
    "temporal": SERVICE_STATUS.UNKNOWN,
    "agent": SERVICE_STATUS.UNKNOWN,
    "temporal-worker": SERVICE_STATUS.UNKNOWN,
}


class ServiceManager(Manager):
    """Manager for `Service` class."""

    def create_services_for(self, node):
        """Create all the services for `node`.

        This makes sure that the `node` has the exact services that should
        be running based on its `node_type`. So if the node_type changes
        this should be called to update the services for `node`.
        """
        # Grab all current services for the node.
        services = {
            service.name: service for service in self.filter(node=node)
        }

        # Expected services that should be on the node.
        expected_services = None
        if node.node_type == NODE_TYPE.REGION_CONTROLLER:
            expected_services = REGION_SERVICES
        elif node.node_type == NODE_TYPE.RACK_CONTROLLER:
            expected_services = RACK_SERVICES
        elif node.node_type == NODE_TYPE.REGION_AND_RACK_CONTROLLER:
            expected_services = REGION_SERVICES | RACK_SERVICES
        else:
            expected_services = frozenset()

        # Remove the any extra services that no longer relate to this node.
        for service_name, service in services.items():
            if service_name not in expected_services:
                service.delete()

        # Create the missing services.
        for service in expected_services:
            if service not in services:
                self.create(
                    node=node, name=service, status=SERVICE_STATUS.UNKNOWN
                )

    def update_service_for(self, node, service, status, status_info=""):
        """Update `service` for `node` with `status`."""
        update_fields = []
        service = self.get(node=node, name=service)
        if service.status != status:
            service.status = status
            update_fields.append("status")
        if service.status_info != status_info:
            service.status_info = status_info
            update_fields.append("status_info")
        if len(update_fields) > 0:
            service.save(update_fields=update_fields)
        return service

    def mark_dead(self, node, dead_region=False, dead_rack=False):
        """Mark all the services on `node` to the correct dead state."""
        dead_services = set()
        if dead_region:
            dead_services |= REGION_SERVICES
        if dead_rack:
            dead_services |= RACK_SERVICES
        for service in self.filter(node=node):
            if service.name in dead_services and service.name in DEAD_STATUSES:
                service.status = DEAD_STATUSES[service.name]
                service.status_info = ""
                service.save()


class Service(CleanSave, TimestampedModel):
    """A service running on regiond or rackd."""

    class Meta:
        unique_together = ("node", "name")
        ordering = ["id"]

    objects = ServiceManager()

    node = ForeignKey("Node", null=False, editable=False, on_delete=CASCADE)

    name = CharField(
        max_length=255,
        null=False,
        blank=False,
        editable=False,
        help_text="Name of service. (e.g. maas-dhcpd)",
    )

    status = CharField(
        max_length=10,
        null=False,
        blank=False,
        choices=SERVICE_STATUS_CHOICES,
        default=SERVICE_STATUS.UNKNOWN,
        editable=False,
    )

    status_info = CharField(
        max_length=255, null=False, blank=True, editable=False
    )

    def __str__(self):
        info = f"{self.name} - {self.status}"
        if len(self.status_info) > 0 and not self.status_info.isspace():
            info += " (%s)" % self.status_info
        return info
