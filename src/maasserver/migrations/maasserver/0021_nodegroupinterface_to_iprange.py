from django.db import migrations, models

# This is a copy/paste from maasserver/models/subnet.py; since migrations don't
# have access to the full model class (and the model class might change over
# time), it has to be duplicated here.
find_best_subnet_for_ip_query = """
    SELECT DISTINCT
        subnet.*,
        masklen(subnet.cidr) "prefixlen",
        ngi.management "ngi_mgmt",
        nodegroup.status "nodegroup_status"
    FROM maasserver_subnet AS subnet
    LEFT OUTER JOIN maasserver_nodegroupinterface AS ngi
        ON ngi.subnet_id = subnet.id
    INNER JOIN maasserver_vlan AS vlan
        ON subnet.vlan_id = vlan.id
    LEFT OUTER JOIN maasserver_nodegroup AS nodegroup
      ON ngi.nodegroup_id = nodegroup.id
    WHERE
        %s << subnet.cidr AND %s << subnet.cidr
    ORDER BY
        /* For nodegroup_status, 1=ENABLED, 2=DISABLED, and NULL
           means the outer join didn't find a related NodeGroup. */
        nodegroup_status NULLS LAST,
        /* For ngi_mgmt, higher numbers indicate "more management".
           (and NULL indicates lack of a related NodeGroupInterface. */
        ngi_mgmt DESC NULLS LAST,
        /* If there are multiple (or no) subnets related to a NodeGroup,
           we'll want to pick the most specific one that the IP address
           falls within. */
        prefixlen DESC
    LIMIT 1
    """


def get_valid_ip_range(low, high):
    if low is not None and low != "" and high is not None and high != "":
        return low, high
    else:
        return None, None


def add_ip_range(IPRange, Subnet, type, low, high, ngi):
    if low is not None and high is not None:
        subnets = Subnet.objects.raw(
            find_best_subnet_for_ip_query, [low, high]
        )
        for subnet in subnets:
            # There will only ever be one or zero due to the LIMIT 1.
            comment = "Migrated from MAAS 1.x"
            iprange, created = IPRange.objects.get_or_create(
                start_ip=low,
                end_ip=high,
                defaults={
                    "comment": comment,
                    "created": ngi.created,
                    "updated": ngi.updated,
                    "type": type,
                    "subnet": subnet,
                },
            )
            # When migrating ranges, put more trust in managed interfaces.
            # (Just in case a disabled or unmanaged range overlaps exactly with
            # a managed range.)
            if not created and ngi.management > 0:
                iprange.type = type
                iprange.subnet = subnet
                iprange.created = ngi.created
                iprange.updated = ngi.updated
                iprange.comment = comment
                iprange.save()


def create_ipranges_from_nodegroupinterfaces(apps, schema_editor):
    NodeGroupInterface = apps.get_model("maasserver", "NodeGroupInterface")
    IPRange = apps.get_model("maasserver", "IPRange")
    Subnet = apps.get_model("maasserver", "Subnet")
    for ngi in NodeGroupInterface.objects.all():
        low, high = get_valid_ip_range(ngi.ip_range_low, ngi.ip_range_high)
        add_ip_range(IPRange, Subnet, "dynamic", low, high, ngi)
        low, high = get_valid_ip_range(
            ngi.static_ip_range_low, ngi.static_ip_range_high
        )
        add_ip_range(IPRange, Subnet, "managed_static", low, high, ngi)


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0020_nodegroup_to_rackcontroller")]

    operations = [
        migrations.RunPython(create_ipranges_from_nodegroupinterfaces)
    ]
