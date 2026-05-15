import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";

export type Selected = {
  linkId?: NetworkLink["id"] | null;
  nicId?: NetworkInterface["id"] | null;
};

export type SetSelected = (selected: Selected[]) => void;
