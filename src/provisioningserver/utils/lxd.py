# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""LXD utilities."""


from collections import defaultdict
from dataclasses import dataclass, field
import re
from typing import List


# This is needed on the rack controller in the LXDPodDriver to set
# the cpu_speed for discovered machines as the lxd resources are
# sent back to the region in a separate thread.
def lxd_cpu_speed(data):
    _, cpu_speed, _, _ = parse_lxd_cpuinfo(data)
    return cpu_speed


@dataclass
class NUMANode:
    memory: int = 0
    cores: List = field(default_factory=list)
    hugepages: int = 0


def parse_lxd_cpuinfo(data):
    cpu_speed = 0
    cpu_model = None
    cpu_count = data.get("cpu", {}).get("total", 0)
    # Only update the cpu_model if all the socket names match.
    sockets = data.get("cpu", {}).get("sockets", [])
    names = []
    numa_nodes = defaultdict(NUMANode)
    for socket in sockets:
        name = socket.get("name")
        if name is not None:
            names.append(name)
        for core in socket.get("cores", []):
            for thread in core.get("threads", []):
                thread_id = thread["id"]
                numa_node = thread["numa_node"]
                numa_nodes[numa_node].cores.append(thread_id)

    if len(names) > 0 and all(name == names[0] for name in names):
        cpu = names[0]
        m = re.search(r"(?P<model_name>.+)", cpu, re.MULTILINE)
        if m is not None:
            cpu_model = m.group("model_name")
            if "@" in cpu_model:
                cpu_model = cpu_model.split(" @")[0]

        # Some CPU vendors include the speed in the model. If so use
        # that for the CPU speed as the other speeds are effected by
        # CPU scaling.
        m = re.search(r"(\s@\s(?P<ghz>\d+\.\d+)GHz)$", cpu, re.MULTILINE)
        if m is not None:
            cpu_speed = int(float(m.group("ghz")) * 1000)
    # When socket names don't match or cpu_speed couldn't be retrieved,
    # use the max frequency among all the sockets if before
    # resulting to average current frequency of all the sockets.
    if not cpu_speed:
        max_frequency = 0
        for socket in sockets:
            frequency_turbo = socket.get("frequency_turbo", 0)
            if frequency_turbo > max_frequency:
                max_frequency = frequency_turbo
        if max_frequency:
            cpu_speed = max_frequency
        else:
            current_average = 0
            for socket in sockets:
                current_average += socket.get("frequency", 0)
            if current_average:
                # Fall back on the current speed, round it to
                # the nearest hundredth as the number may be
                # effected by CPU scaling.
                current_average /= len(sockets)
                cpu_speed = round(current_average / 100) * 100

    return cpu_count, cpu_speed, cpu_model, numa_nodes


def parse_lxd_networks(networks):
    """Return a dict with interface names and their details from networks info.

    This function is meant to be called with the content of the "networks"
    section output from the machine-resources binary.
    This would be a dict with interface name and details that match the output
    of the LXD /1.0/network/<iface>/state endpoint.

    """
    interfaces = {}
    for name, details in networks.items():
        interface = {
            "type": details["type"],
            "mac": details["hwaddr"],
            "enabled": details["state"] == "up",
            "addresses": [
                f"{address['address']}/{address['netmask']}"
                for address in details["addresses"]
                # skip link-local addresses
                if address["scope"] != "link"
            ],
            "parents": [],
        }
        if details["bridge"]:
            interface["type"] = "bridge"
            interface["parents"] = details["bridge"]["upper_devices"]
        elif details["bond"]:
            interface["type"] = "bond"
            interface["parents"] = details["bond"]["lower_devices"]
        elif (
            details.get("vlan") is not None
        ):  # key could be missing for old versions
            interface["type"] = "vlan"
            interface["vid"] = details["vlan"]["vid"]
            interface["parents"] = [details["vlan"]["lower_device"]]
        interfaces[name] = interface

    return interfaces
