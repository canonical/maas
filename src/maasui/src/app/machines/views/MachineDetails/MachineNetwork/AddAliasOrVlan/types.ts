import type { NetworkValues } from "../NetworkFields/NetworkFields";

import type { NetworkInterface } from "@/app/store/types/node";

export type AddAliasOrVlanValues = NetworkValues & {
  tags?: NetworkInterface["tags"];
};
