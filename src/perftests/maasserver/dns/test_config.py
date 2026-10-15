# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasserver.dns.config import dns_update_all_zones


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

    with perf.record("test_perf_full_dns_reload.zonefile_rewrite"):
        dns_update_all_zones()
