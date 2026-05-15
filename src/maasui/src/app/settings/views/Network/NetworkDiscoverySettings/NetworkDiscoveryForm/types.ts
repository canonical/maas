import type { NetworkDiscovery } from "@/app/store/config/types";

export type NetworkDiscoveryValues = {
  active_discovery_interval?: string;
  network_discovery: NetworkDiscovery | "";
};
