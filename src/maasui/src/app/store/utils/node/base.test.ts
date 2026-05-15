import {
  canOpenActionForm,
  isNodeDetails,
  nodeIsController,
  nodeIsDevice,
  nodeIsMachine,
} from "./base";

import { NodeActions, NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";

describe("node utils", () => {
  describe("nodeIsController", () => {
    it("correctly identifies a node as a controller", () => {
      expect(nodeIsController(factory.controller())).toBe(true);
      expect(nodeIsController(factory.device())).toBe(false);
      expect(nodeIsController(factory.machine())).toBe(false);
      expect(nodeIsController(null)).toBe(false);
      expect(nodeIsController()).toBe(false);
    });
  });

  describe("nodeIsDevice", () => {
    it("correctly identifies a node as a device", () => {
      expect(nodeIsDevice(factory.controller())).toBe(false);
      expect(nodeIsDevice(factory.device())).toBe(true);
      expect(nodeIsDevice(factory.machine())).toBe(false);
      expect(nodeIsDevice(null)).toBe(false);
      expect(nodeIsDevice()).toBe(false);
    });
  });

  describe("nodeIsMachine", () => {
    it("correctly identifies a node as a machine", () => {
      expect(nodeIsMachine(factory.controller())).toBe(false);
      expect(nodeIsMachine(factory.device())).toBe(false);
      expect(nodeIsMachine(factory.machine())).toBe(true);
      expect(nodeIsMachine(null)).toBe(false);
      expect(nodeIsMachine()).toBe(false);
    });
  });

  describe("isNodeDetails", () => {
    it("correctly identifies nodes as details", () => {
      expect(isNodeDetails(factory.controllerDetails())).toBe(true);
      expect(isNodeDetails(factory.deviceDetails())).toBe(true);
      expect(isNodeDetails(factory.machineDetails())).toBe(true);
    });

    it("correctly identifies nodes as non-details", () => {
      expect(isNodeDetails(factory.controller())).toBe(false);
      expect(isNodeDetails(factory.device())).toBe(false);
      expect(isNodeDetails(factory.machine())).toBe(false);
    });
  });

  describe("canOpenActionForm", () => {
    it("handles the null case", () => {
      expect(canOpenActionForm(null, null)).toBe(false);
      expect(canOpenActionForm(factory.machine(), null)).toBe(false);
      expect(canOpenActionForm(null, NodeActions.TAG)).toBe(false);
    });

    it("handles whether a node can open an action form", () => {
      const node = factory.device({ actions: [NodeActions.SET_ZONE] });
      expect(canOpenActionForm(node, NodeActions.SET_ZONE)).toBe(true);
      expect(canOpenActionForm(node, NodeActions.DELETE)).toBe(false);
    });

    it("handles whether a machine can open the clone action form", () => {
      const machine1 = factory.machine({
        actions: [NodeActions.CLONE],
        status: NodeStatus.READY,
      });
      const machine2 = factory.machine({
        actions: [],
        status: NodeStatus.READY,
      });
      const machine3 = factory.machine({
        actions: [NodeActions.CLONE],
        status: NodeStatus.NEW,
      });
      const machine4 = factory.machine({
        actions: [],
        status: NodeStatus.NEW,
      });
      expect(canOpenActionForm(machine1, NodeActions.CLONE)).toBe(true);
      expect(canOpenActionForm(machine2, NodeActions.CLONE)).toBe(true);
      expect(canOpenActionForm(machine3, NodeActions.CLONE)).toBe(false);
      expect(canOpenActionForm(machine4, NodeActions.CLONE)).toBe(false);
    });
  });
});
