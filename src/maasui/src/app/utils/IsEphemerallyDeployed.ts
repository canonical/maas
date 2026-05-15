import type { Machine } from "@/app/store/machine/types";
import { NodeStatusCode } from "@/app/store/types/node";

export const isEphemerallyDeployed = (
  machine: Machine | null
): boolean | null => {
  return (
    machine &&
    machine.status_code === NodeStatusCode.DEPLOYED &&
    machine.ephemeral_deploy
  );
};
