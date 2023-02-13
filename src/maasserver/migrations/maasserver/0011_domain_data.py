import datetime

from django.db import migrations, models
import django.db.models.deletion

import maasserver.models.dnsresource
from maasserver.models.domain import DEFAULT_DOMAIN_NAME
import maasserver.models.node


class NODEGROUPINTERFACE_MANAGEMENT:
    """The vocabulary of a `NodeGroupInterface`'s possible statuses."""

    # A nodegroupinterface starts out as UNMANAGED.
    DEFAULT = 0
    #: Do not manage DHCP or DNS for this interface.
    UNMANAGED = 0
    #: Manage DHCP for this interface.
    DHCP = 1
    #: Manage DHCP and DNS for this interface.
    DHCP_AND_DNS = 2


def migrate_nodegroup_name(apps, schema_editor):
    NodeGroup = apps.get_model("maasserver", "NodeGroup")
    Node = apps.get_model("maasserver", "Node")
    Domain = apps.get_model("maasserver", "Domain")

    # First, create the default domain.
    now = datetime.datetime.now()
    domain, _ = Domain.objects.get_or_create(
        id=0,
        defaults={
            "id": 0,
            "name": DEFAULT_DOMAIN_NAME,
            "authoritative": True,
            "created": now,
            "updated": now,
        },
    )

    # Then, create all of the domains for which we are authoritative
    for nodegroup in NodeGroup.objects.filter(name__isnull=False):
        # Create a Domain if needed, for this name.
        now = datetime.datetime.now()
        domain, _ = Domain.objects.get_or_create(
            name=nodegroup.name,
            authoritative=True,
            defaults={"created": nodegroup.created, "updated": now},
        )

    # Now go through all the nodegroups:
    # 1. Fix the node hostnames, creating non-authoritative domains as needed.
    #    If the node is on any DNS-managing NodeGroupInterface, then we throw
    #    away the domainname.  If we do not manage DNS here, then honor the DNS
    #    name by creating (or using) a non-auth domain.
    # 2. Set node.domain appropriately
    for nodegroup in NodeGroup.objects.filter(name__isnull=False):
        ngi = nodegroup.nodegroupinterface_set.filter(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS
        )
        domain = Domain.objects.get(name=nodegroup.name)
        for node in nodegroup.node_set.all():
            if node.hostname.find(".") > -1:
                name, domainname = node.hostname.split(".", 1)
                node.hostname = name
                managed_ngi = node.interface_set.filter(
                    ip_addresses__subnet__nodegroupinterface__in=ngi
                ).distinct()
                now = datetime.datetime.now()
                this_domain, _ = Domain.objects.get_or_create(
                    name=domainname,
                    defaults={
                        "authoritative": False,
                        "created": node.created,
                        "updated": now,
                    },
                )
                if managed_ngi.count() == 0:
                    node.domain = this_domain
                else:
                    node.domain = domain
            else:
                node.domain = domain
            node.save()


def migrate_staticipaddress_hostname(apps, schema_editor):
    StaticIPAddress = apps.get_model("maasserver", "StaticIPAddress")
    Domain = apps.get_model("maasserver", "Domain")
    DNSResource = apps.get_model("maasserver", "DNSResource")

    # move hostname from StaticIPAddress to DNSResource
    ips = StaticIPAddress.objects.filter(hostname__isnull=False).exclude(
        hostname=""
    )
    for ip in ips:
        hostname = ip.hostname.split(".")[0]
        domains = {
            interface.node.domain
            for interface in ip.interface_set.filter(node__isnull=False)
        }
        if len(domains):
            domain_id = domains.pop().id
        else:
            domain_id = maasserver.models.dnsresource.get_default_domain()
        now = datetime.datetime.now()
        dnsrr, _ = DNSResource.objects.get_or_create(
            name=hostname,
            domain_id=domain_id,
            defaults={"created": ip.created, "updated": now},
        )
        dnsrr.ip_addresses.add(ip)
        dnsrr.save()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0010_add_dns_models")]

    operations = [
        migrations.RunPython(migrate_nodegroup_name),
        migrations.RunPython(migrate_staticipaddress_hostname),
    ]
