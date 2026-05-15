import type { Controller } from "@/app/store/controller/types";
import { isControllerDetails } from "@/app/store/controller/utils";
import type { Device } from "@/app/store/device/types";
import { isDeviceDetails } from "@/app/store/device/utils";
import type { Machine } from "@/app/store/machine/types";
// Import from the common utils to prevent an import loop in machine/utils/index.ts.
import { isMachineDetails } from "@/app/store/machine/utils/common";
import type { PodActions } from "@/app/store/pod/types/base";
import type { Node, NodeDetails } from "@/app/store/types/node";
import {
  NodeActions,
  NodeLinkType,
  NodeStatus,
  NodeType,
  NodeTypeDisplay,
} from "@/app/store/types/node";

/**
 * Get node type display from node type.
 * @param nodeType - The type of the node.
 * @returns Node type display.
 */
export const getNodeTypeDisplay = (nodeType: NodeType): string => {
  switch (nodeType) {
    case NodeType.DEFAULT:
    case NodeType.MACHINE:
      return NodeTypeDisplay.MACHINE;
    case NodeType.DEVICE:
      return NodeTypeDisplay.DEVICE;
    case NodeType.RACK_CONTROLLER:
      return NodeTypeDisplay.RACK_CONTROLLER;
    case NodeType.REGION_CONTROLLER:
      return NodeTypeDisplay.REGION_CONTROLLER;
    case NodeType.REGION_AND_RACK_CONTROLLER:
      return NodeTypeDisplay.REGION_AND_RACK_CONTROLLER;
    default:
      return "Unknown";
  }
};

/**
 * Get title from node action name.
 * @param actionName - The name of the node action to check.
 * @returns Formatted node action title.
 */
export const getNodeActionTitle = (actionName: NodeActions): string => {
  const actionTitles: Record<NodeActions, string> = {
    [NodeActions.ABORT]: "Abort",
    [NodeActions.ACQUIRE]: "Allocate",
    [NodeActions.CHECK_POWER]: "Check power",
    [NodeActions.CLONE]: "Clone from",
    [NodeActions.COMMISSION]: "Commission",
    [NodeActions.DELETE]: "Delete",
    [NodeActions.DEPLOY]: "Deploy",
    [NodeActions.EXIT_RESCUE_MODE]: "Exit rescue mode",
    [NodeActions.IMPORT_IMAGES]: "Import images",
    [NodeActions.LOCK]: "Lock",
    [NodeActions.MARK_BROKEN]: "Mark broken",
    [NodeActions.MARK_FIXED]: "Mark fixed",
    [NodeActions.OFF]: "Power off",
    [NodeActions.ON]: "Power on",
    [NodeActions.OVERRIDE_FAILED_TESTING]: "Override failed testing",
    [NodeActions.POWER_CYCLE]: "Power cycle",
    [NodeActions.RELEASE]: "Release",
    [NodeActions.RESCUE_MODE]: "Enter rescue mode",
    [NodeActions.SET_POOL]: "Set pool",
    [NodeActions.SET_ZONE]: "Set zone",
    [NodeActions.SOFT_OFF]: "Soft power off",
    [NodeActions.TAG]: "Tag",
    [NodeActions.TEST]: "Test",
    [NodeActions.UNTAG]: "Untag",
    [NodeActions.UNLOCK]: "Unlock",
  };

  return actionTitles[actionName] || "Action";
};
export const getNodeActionLabel = (
  modelString: string,
  actionName: NodeActions | PodActions,
  isProcessing: boolean
): string => {
  const actionLabels: Record<NodeActions | PodActions, string[]> = {
    [NodeActions.ABORT]: [
      `Abort actions for ${modelString}`,
      `Aborting actions for ${modelString}`,
    ],
    [NodeActions.ACQUIRE]: [
      `Allocate ${modelString}`,
      `Allocating ${modelString}`,
    ],
    [NodeActions.CHECK_POWER]: [
      `Check power for ${modelString}`,
      `Checking power for ${modelString}`,
    ],
    [NodeActions.CLONE]: [`Clone to ${modelString}`, `Cloning in progress`],
    [NodeActions.COMMISSION]: [
      `Start commissioning for ${modelString}`,
      `Starting commissioning for ${modelString}`,
    ],
    [NodeActions.DELETE]: [`Delete ${modelString}`, `Deleting ${modelString}`],
    [NodeActions.DEPLOY]: [`Deploy ${modelString}`, `Deploying ${modelString}`],
    [NodeActions.EXIT_RESCUE_MODE]: [
      `Exit rescue mode for ${modelString}`,
      `Exiting rescue mode for ${modelString}`,
    ],
    [NodeActions.IMPORT_IMAGES]: [
      `Import images for ${modelString}`,
      `Importing images for ${modelString}`,
    ],
    [NodeActions.LOCK]: [`Lock ${modelString}`, `Locking ${modelString}`],
    [NodeActions.ON]: [`Power on ${modelString}`, `Powering on ${modelString}`],
    [NodeActions.OFF]: [
      `Power off ${modelString}`,
      `Powering off ${modelString}`,
    ],
    [NodeActions.MARK_BROKEN]: [
      `Mark ${modelString} broken`,
      `Marking ${modelString} broken`,
    ],
    [NodeActions.MARK_FIXED]: [
      `Mark ${modelString} fixed`,
      `Marking ${modelString} fixed`,
    ],
    [NodeActions.OVERRIDE_FAILED_TESTING]: [
      `Override failed tests for ${modelString}`,
      `Overriding failed tests for ${modelString}`,
    ],
    [NodeActions.POWER_CYCLE]: [
      `Power cycle ${modelString}`,
      `Power cycling ${modelString}`,
    ],
    [NodeActions.RELEASE]: [
      `Release ${modelString}`,
      `Releasing ${modelString}`,
    ],
    [NodeActions.RESCUE_MODE]: [
      `Enter rescue mode for ${modelString}`,
      `Entering rescue mode for ${modelString}`,
    ],
    [NodeActions.SET_POOL]: [
      `Set pool for ${modelString}`,
      `Setting pool for ${modelString}`,
    ],
    [NodeActions.SET_ZONE]: [
      `Set zone for ${modelString}`,
      `Setting zone for ${modelString}`,
    ],
    [NodeActions.SOFT_OFF]: [
      `Soft power off ${modelString}`,
      `Powering off ${modelString}`,
    ],
    [NodeActions.TAG]: [
      `Update tags for ${modelString}`,
      `Updating tags for ${modelString}`,
    ],
    [NodeActions.UNTAG]: [
      `Update tags for ${modelString}`,
      `Updating tags for ${modelString}`,
    ],
    [NodeActions.TEST]: [
      `Start tests for ${modelString}`,
      `Starting tests for ${modelString}`,
    ],
    [NodeActions.UNLOCK]: [`Unlock ${modelString}`, `Unlocking ${modelString}`],
    compose: [`Compose ${modelString}`, `Composing ${modelString}`],
    refresh: [`Refresh ${modelString}`, `Refreshing ${modelString}`],
    remove: [`Remove ${modelString}`, `Removing ${modelString}`],
  };

  const label = actionLabels[actionName];
  if (Array.isArray(label)) {
    const [actionLabel, actionProcessingLabel] = label;
    return isProcessing ? actionProcessingLabel : actionLabel;
  }

  return `${isProcessing ? "Processing" : "Process"} ${modelString}`;
};

// TODO: Replace NodeLinkType with NodeType when it is made available on all
// node list types.
// https://bugs.launchpad.net/maas/+bug/1951893
/**
 * Returns whether a node is a controller.
 * @param node - The node to check
 * @returns Whether the node is a controller.
 */
export const nodeIsController = (node?: Node | null): node is Controller =>
  node?.link_type === NodeLinkType.CONTROLLER;

/**
 * Returns whether a node is a device.
 * @param node - The node to check
 * @returns Whether the node is a device.
 */
export const nodeIsDevice = (node?: Node | null): node is Device =>
  node?.link_type === NodeLinkType.DEVICE;

/**
 * Returns whether a node is a machine.
 * @param node - The node to check
 * @returns Whether the node is a machine.
 */
export const nodeIsMachine = (node?: Node | null): node is Machine =>
  node?.link_type === NodeLinkType.MACHINE;

/**
 * Returns whether a node is the details version of the node type.
 * @param node - The node to check.
 * @returns Whether the node is a details type.
 */
export const isNodeDetails = (node?: Node | null): node is NodeDetails =>
  (nodeIsController(node) && isControllerDetails(node)) ||
  (nodeIsDevice(node) && isDeviceDetails(node)) ||
  (nodeIsMachine(node) && isMachineDetails(node));

/**
 * Determine whether a node can open an action form for a particular action.
 * @param node - The node to check.
 * @param actionName - The name of the action to check, e.g. "commission"
 * @returns Whether the node can open the action form.
 */
export const canOpenActionForm = (
  node: Node | null,
  actionName: NodeActions | null
): boolean => {
  if (!node || !actionName) {
    return false;
  }

  if (nodeIsMachine(node) && actionName === NodeActions.CLONE) {
    // Cloning in the UI works inverse to the rest of the machine actions - we
    // select the destination machines first then when the form is open we
    // select the machine to actually perform the clone action. The destination
    // machines can only be in a subset of statuses.
    return [NodeStatus.READY, NodeStatus.FAILED_TESTING].includes(node.status);
  }

  if (nodeIsMachine(node) && actionName === NodeActions.CHECK_POWER) {
    // "Check power" is always shown for machines, even though it's not listed in node.actions.
    return true;
  }
  return node.actions.some((nodeAction) => nodeAction === actionName);
};
