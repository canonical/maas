import { useCanEdit } from "./node";

import type { Node } from "@/app/store/types/node";
import { NodeStatus } from "@/app/store/types/node";
import { nodeIsController, nodeIsDevice } from "@/app/store/utils";

/**
 * Check if the networking information can be edited.
 * @return Whether networking is disabled.
 */
export const useIsAllNetworkingDisabled = (node?: Node | null): boolean => {
  const canEdit = useCanEdit(node, true);
  if (!node) {
    return true;
  }
  if (nodeIsController(node)) {
    // Networking is read only for controllers.
    return true;
  }
  if (nodeIsDevice(node)) {
    // Never disable the full networking panel when its a Device.
    return false;
  }
  return (
    !canEdit ||
    ![
      NodeStatus.NEW,
      NodeStatus.READY,
      NodeStatus.FAILED_TESTING,
      NodeStatus.ALLOCATED,
      NodeStatus.BROKEN,
    ].includes(node.status)
  );
};
