import re

from django.db import connection, migrations

from maasserver.enum import IPADDRESS_TYPE
from maasserver.models import timestampedmodel
from provisioningserver.drivers.power.registry import PowerDriverRegistry


# Derived from Subnet model.
def raw_subnet_id_containing_ip(ip):
    """Find the most specific Subnet the specified IP address belongs in."""
    find_subnets_with_ip_query = """
        SELECT DISTINCT subnet.id, masklen(subnet.cidr) "prefixlen"
        FROM
            maasserver_subnet AS subnet
        WHERE
            %s << subnet.cidr
        ORDER BY prefixlen DESC
        """
    cursor = connection.cursor()
    cursor.execute(find_subnets_with_ip_query, [str(ip)])
    row = cursor.fetchone()
    if row is not None:
        return row[0]
    else:
        return None


# Copied from BMC model.
def extract_ip_address(power_type, power_parameters):
    # Extract the ip_address from the power_parameters. If there is no
    # power_type, no power_parameters, or no valid value provided in the
    # power_address field, returns None.
    if not power_type or not power_parameters:
        return None
    power_driver = PowerDriverRegistry.get_item(power_type)
    if power_driver is None:
        return None
    power_type_parameters = power_driver.settings
    if not power_type_parameters:
        return None
    ip_extractor = power_driver.ip_extractor
    if not ip_extractor:
        return None
    field_value = power_parameters.get(ip_extractor.get("field_name"))
    if not field_value:
        return None
    extraction_pattern = ip_extractor.get("pattern")
    if not extraction_pattern:
        return None
    match = re.match(extraction_pattern, field_value)
    return match.group("address") if match else None


# Copied from Node.update_power_type_and_parameters().
def create_staticipaddresses_for_bmcs(apps, schema_editor):
    now = timestampedmodel.now()
    BMC = apps.get_model("maasserver", "BMC")
    StaticIPAddress = apps.get_model("maasserver", "StaticIPAddress")

    for bmc in BMC.objects.all().order_by("id"):
        # parse power_parameters and create new ip addresses
        new_ip = extract_ip_address(bmc.power_type, bmc.power_parameters)
        old_ip = bmc.ip_address.ip if bmc.ip_address else None
        if new_ip != old_ip:
            try:
                if new_ip is None:
                    # Set ip to None, save, then delete the old ip.
                    old_ip_address = bmc.ip_address
                    bmc.ip_address = None
                    bmc.save()
                    if old_ip_address is not None:
                        old_ip_address.delete()
                else:
                    subnet_id = raw_subnet_id_containing_ip(new_ip)
                    # Update or create new StaticIPAddress.
                    if bmc.ip_address:
                        bmc.ip_address.ip = new_ip
                        bmc.ip_address.subnet_id = subnet_id
                        bmc.ip_address.save()
                    else:
                        ip_address = StaticIPAddress(
                            created=now,
                            updated=now,
                            subnet_id=subnet_id,
                            ip=new_ip,
                            alloc_type=IPADDRESS_TYPE.STICKY,
                        )
                        ip_address.save()
                        bmc.ip_address = ip_address
                        bmc.save()
            except Exception:
                # Extracting the IP is best-effort.
                pass


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0021_nodegroupinterface_to_iprange")]

    operations = [migrations.RunPython(create_staticipaddresses_for_bmcs)]
