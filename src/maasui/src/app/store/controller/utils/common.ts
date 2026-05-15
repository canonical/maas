import type {
  Controller,
  ControllerDetails,
} from "@/app/store/controller/types";
import { NodeType } from "@/app/store/types/node";

/**
 * Returns whether a controller is of type ControllerDetails.
 * @param controller - The controller to check
 * @returns Whether the controller is of type ControllerDetails.
 */
export const isControllerDetails = (
  controller?: Controller | null
  // Use "interfaces" as the canary as it only exists for ControllerDetails.
): controller is ControllerDetails =>
  !!controller && "interfaces" in controller;

/**
 * Returns whether a controller is a rack controller.
 * @param controller - The controller to check
 * @returns Whether the controller is a rack controller
 */
export const isRack = (controller?: Controller | null): boolean =>
  controller?.node_type === NodeType.RACK_CONTROLLER;

/**
 * Returns whether a controller is a region controller.
 * @param controller - The controller to check
 * @returns Whether the controller is a region controller
 */
export const isRegion = (controller?: Controller | null): boolean =>
  controller?.node_type === NodeType.REGION_CONTROLLER;

/**
 * Returns whether a controller is a region+rack controller.
 * @param controller - The controller to check
 * @returns Whether the controller is a region+rack controller
 */
export const isRegionAndRack = (controller?: Controller | null): boolean =>
  controller?.node_type === NodeType.REGION_AND_RACK_CONTROLLER;
