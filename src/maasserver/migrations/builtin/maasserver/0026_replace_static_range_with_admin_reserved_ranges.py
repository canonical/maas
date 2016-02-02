# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime

from django.db import (
    migrations,
    models,
)
# Need a copy of this enum as it existed pre-migration.
from netaddr import IPAddress
from provisioningserver.utils.network import (
    MAASIPSet,
    make_iprange,
)


class IPRANGE_TYPE:
    """The vocabulary of possible types of `IPRange` objects."""

    # Managed by MAAS DHCP.
    MANAGED_DHCP = 'managed_dhcp'

    # Managed by an external DHCP server.
    UNMANAGED_DHCP = 'unmanaged_dhcp'

    # Reserved administratively. This is like an "inverse static range";
    # IP addresses that MAAS is specifically not allowed to touch.
    ADMIN_RESERVED = 'admin_reserved'

    # Reserved for exclusive use by a particular user.
    USER_RESERVED = 'user_reserved'

    # MAAS-managed static IP address range.
    MANAGED_STATIC = 'managed_static'


def convert_static_ipranges_to_reserved(
        IPRange, subnet, ranges, created_time, range_description):
    unreserved_range_set = MAASIPSet(ranges)
    unreserved_ranges = unreserved_range_set.get_unused_ranges(
        subnet.cidr, comment="reserved")
    for iprange in unreserved_ranges:
        start_ip = str(IPAddress(iprange.first))
        end_ip = str(IPAddress(iprange.last))
        IPRange.objects.get_or_create(
            created=created_time, updated=datetime.now(),
            subnet=subnet, start_ip=start_ip, end_ip=end_ip,
            type=IPRANGE_TYPE.ADMIN_RESERVED,
            comment="Migrated from static range: %s on %s." %
                    (range_description, subnet.cidr))


def migrate_static_ranges_to_admin_reserved(apps, schema_editor):
    Subnet = apps.get_model("maasserver", "Subnet")
    IPRange = apps.get_model("maasserver", "IPRange")
    for subnet in Subnet.objects.all():
        static_range = subnet.iprange_set.filter(
            type=IPRANGE_TYPE.MANAGED_STATIC).first()
        if static_range is None:
            continue
        created_time = static_range.created
        reserved_ranges = [
            make_iprange(iprange.start_ip, iprange.end_ip, iprange.type)
            for iprange in
            subnet.iprange_set.filter(
                type__in=[IPRANGE_TYPE.MANAGED_STATIC,
                          IPRANGE_TYPE.MANAGED_DHCP,
                          IPRANGE_TYPE.UNMANAGED_DHCP])
        ]
        convert_static_ipranges_to_reserved(
            IPRange, subnet, reserved_ranges, created_time,
            "%s-%s" % (static_range.start_ip, static_range.end_ip))
        subnet.iprange_set.filter(type=IPRANGE_TYPE.MANAGED_STATIC).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('maasserver', '0025_create_zone_serial_sequence'),
    ]

    operations = [
        migrations.RunPython(migrate_static_ranges_to_admin_reserved),
    ]
