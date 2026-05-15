import type { NetworkValues } from "../NetworkFields/NetworkFields";

import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";

export type EditPhysicalValues = NetworkValues & {
  interface_speed: NetworkInterface["interface_speed"];
  link_id: NetworkLink["id"] | "";
  link_speed: NetworkInterface["link_speed"];
  mac_address: NetworkInterface["mac_address"];
  name?: NetworkInterface["name"];
  tags?: NetworkInterface["tags"];
};
