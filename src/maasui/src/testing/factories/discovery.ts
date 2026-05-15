import { extend, random } from "cooky-cutter";

import { timestamp } from "./general";
import { model } from "./model";

import type { DiscoveryResponse } from "@/app/apiclient";
import type { Model } from "@/app/store/types/model";

export const discovery = extend<Model, DiscoveryResponse>(model, {
  discovery_id: () => `discovery-${random()}`,
  fabric_name: "fabric-1",
  fabric_id: 1,
  first_seen: "1502597995.5000",
  hostname: "discovery-hostname",
  ip: "192.168.1.1",
  is_external_dhcp: false,
  last_seen: () => timestamp("Wed, 08 Jul. 2020 05:35:4"),
  mac_address: "00:00:00:00:00:00",
  mac_organization: "Unknown Vendor",
  mdns_id: 2,
  neighbour_id: 3,
  observer_hostname: "observer-hostname",
  observer_interface_name: "iface-name",
  observer_interface_id: 4,
  observer_system_id: "abc123",
  observer_id: 5,
  subnet_cidr: "192.168.1.1/24",
  subnet_id: 6,
  vid: 7,
  vlan_id: 5001,
});
