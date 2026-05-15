import type { Node } from "../types/node";
import { NodeType } from "../types/node";

import urls from "@/app/base/urls";

export const getNodeUrl = (
  type: NodeType,
  system_id: Node["system_id"]
): string => {
  switch (type) {
    case NodeType.MACHINE:
      return urls.machines.machine.index({ id: system_id });
    case NodeType.DEVICE:
      return urls.devices.device.index({ id: system_id });
    default:
      return urls.controllers.controller.index({ id: system_id });
  }
};
