# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasserver.dns.config import (
    dns_update_all_zones,
    process_dns_update_notify,
)
from provisioningserver.dns.config import DynamicDNSUpdate


@pytest.mark.usefixtures("maasdb")
def test_perf_full_dns_reload(
    perf, dns_config_path, zone_file_config_path, bind_server, factory
):
    domains = [factory.make_Domain() for _ in range(5)]
    subnet = factory.make_Subnet(cidr="10.0.0.0/24")
    ips = [factory.make_StaticIPAddress(subnet=subnet) for _ in range(100)]
    [
        factory.make_DNSResource(domain=domains[i % 5], ip_addresses=[ips[i]])
        for i in range(100)
    ]

    with perf.record("test_perf_full_dns_reload.zonefile_write"):
        dns_update_all_zones()

    # zonefile already written, sends dynamic update instead
    with perf.record("test_perf_full_dns_reload.dynamic_update"):
        dns_update_all_zones()


@pytest.mark.usefixtures("maasdb")
def test_perf_generate_dns_updates(perf, factory):
    domain = factory.make_Domain()
    subnet = factory.make_Subnet(cidr="10.0.0.0/24")
    ips = [factory.make_StaticIPAddress(subnet=subnet) for _ in range(100)]
    records = [
        factory.make_DNSResource(domain=domain, ip_addresses=[ips[i]])
        for i in range(100)
    ]

    with perf.record("test_perf_generate_dns_updates.forward"):
        for record in records:
            notify = f"INSERT {domain.name} {record.name} A 30 {record.ip_addresses.first()}"
            process_dns_update_notify(notify)

    with perf.record("test_perf_generate_dns_updates.reverse"):
        for record in records:
            notify = f"INSERT {domain.name} {record.name} A 30 {record.ip_addresses.first()}"
            fwd, _ = process_dns_update_notify(notify)
            DynamicDNSUpdate.as_reverse_record_update(fwd[0], subnet.cidr)
