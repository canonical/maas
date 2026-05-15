import type { Fabric, FabricMeta } from "@/app/store/fabric/types";
import type { Space, SpaceMeta } from "@/app/store/space/types";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";
import { argPath, isId } from "@/app/utils";

const withSubnetId = argPath<{ id: Subnet[SubnetMeta.PK] }>;

const urls = {
  index: "/networks",
  fabrics: {
    index: "/networks/fabrics",
  },
  spaces: {
    index: "/networks/spaces",
  },
  subnets: {
    index: "/networks/subnets",
    indexWithParams: (options: { by?: string; q?: string }): string => {
      const defaults = { by: "fabric", q: "" };
      const { by, q } = { ...defaults, ...options };
      return `/networks/subnets?by=${by}&q=${q}`;
    },
  },
  vlans: {
    index: "/networks/vlans",
  },
  fabric: {
    index: argPath<{ id: Fabric[FabricMeta.PK] }>("/fabric/:id"),
  },
  space: {
    index: argPath<{ id: Space[SpaceMeta.PK] }>("/space/:id"),
  },
  subnet: {
    summary: withSubnetId("/subnet/:id/summary"),
    staticRoutes: withSubnetId("/subnet/:id/static-routes"),
    addressReservation: withSubnetId("/subnet/:id/address-reservation"),
    dhcpSnippets: withSubnetId("/subnet/:id/dhcp-snippets"),
    usedIpAddresses: withSubnetId("/subnet/:id/used-ip-addresses"),
    index: argPath<{ id: Subnet[SubnetMeta.PK] }>("/subnet/:id"),
  },
  vlan: {
    index: argPath<{ id: VLAN[VLANMeta.PK] }>("/vlan/:id"),
  },
} as const;

const getFabricLink = (id?: Fabric["id"]): string | null =>
  isId(id) ? urls.fabric.index({ id }) : null;
const getSpaceLink = (id?: Space["id"]): string | null =>
  isId(id) ? urls.space.index({ id }) : null;
const getVLANLink = (id?: VLAN["id"]): string | null =>
  isId(id) ? urls.vlan.index({ id }) : null;
const getSubnetLink = (id?: Subnet["id"]): string | null =>
  isId(id) ? urls.subnet.index({ id }) : null;

export default urls;
export { getFabricLink, getSpaceLink, getSubnetLink, getVLANLink };
