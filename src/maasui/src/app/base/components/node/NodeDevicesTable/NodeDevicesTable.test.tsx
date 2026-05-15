import { describe } from "vitest";

import NodeDevicesTable from "./NodeDevicesTable";

import { HardwareType } from "@/app/base/enum";
import urls from "@/app/base/urls";
import CommissionForm from "@/app/machines/components/MachineForms/MachineActionFormWrapper/CommissionForm";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { NodeDeviceBus } from "@/app/store/nodedevice/types";
import type { RootState } from "@/app/store/root/types";
import { NodeActions, NodeStatusCode } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  waitFor,
  userEvent,
  mockSidePanel,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("NodeDevicesTable", () => {
  let state: RootState;
  let machine: MachineDetails;
  let controller: ControllerDetails;

  beforeEach(() => {
    machine = factory.machineDetails({ system_id: "abc123" });
    controller = factory.controllerDetails({ system_id: "abc123" });
    const networkDevice = factory.nodeDevice({
      bus: NodeDeviceBus.PCIE,
      hardware_type: HardwareType.Network,
      node_id: machine.id,
    });
    const storageDevice = factory.nodeDevice({
      bus: NodeDeviceBus.PCIE,
      hardware_type: HardwareType.Storage,
      node_id: machine.id,
    });
    state = factory.rootState({
      nodedevice: factory.nodeDeviceState({
        items: [networkDevice, storageDevice],
      }),
    });
  });

  describe("display", () => {
    it("displays a loading component if pools are loading", async () => {
      state.nodedevice.loading = true;
      renderWithProviders(
        <NodeDevicesTable bus={NodeDeviceBus.PCIE} node={machine} />,
        {
          state,
        }
      );

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    describe("displays a message when rendering an empty list", () => {
      it("prompts user to commission machine if no devices found and machine can be commissioned", async () => {
        const machine = factory.machineDetails({
          actions: [NodeActions.COMMISSION],
        });

        renderWithProviders(
          <NodeDevicesTable bus={NodeDeviceBus.PCIE} node={machine} />,
          { state }
        );

        await waitFor(() => {
          expect(
            screen.getByText(/Try commissioning this machine/i)
          ).toBeInTheDocument();
        });

        await userEvent.click(
          screen.getByRole("button", { name: "Commission" })
        );

        expect(mockOpen).toHaveBeenCalledWith({
          component: CommissionForm,
          title: "Commission machine",
          props: { isViewingDetails: true },
        });
      });

      it("shows a message if the machine has no node devices and is locked", () => {
        const machine = factory.machineDetails({ locked: true });

        renderWithProviders(
          <NodeDevicesTable bus={NodeDeviceBus.PCIE} node={machine} />,
          { state }
        );

        expect(screen.getByText(/The machine is locked/i)).toBeInTheDocument();
      });

      it("shows a message if the machine has no node devices and is in failed testing state", () => {
        const machine = factory.machineDetails({
          status_code: NodeStatusCode.FAILED_TESTING,
        });

        renderWithProviders(
          <NodeDevicesTable bus={NodeDeviceBus.PCIE} node={machine} />,
          { state }
        );

        expect(
          screen.getByText(/Override failed testing/i)
        ).toBeInTheDocument();
      });

      it("shows a message if the machine has no node devices and is deployed", () => {
        const machine = factory.machineDetails({
          status_code: NodeStatusCode.DEPLOYED,
        });

        renderWithProviders(
          <NodeDevicesTable bus={NodeDeviceBus.PCIE} node={machine} />,
          { state }
        );

        expect(screen.getByText(/Release this machine/i)).toBeInTheDocument();
      });

      it("shows a message if the machine has no node devices and is commissioning", () => {
        const machine = factory.machineDetails({
          locked: false,
          status_code: NodeStatusCode.COMMISSIONING,
        });

        renderWithProviders(
          <NodeDevicesTable bus={NodeDeviceBus.PCIE} node={machine} />,
          { state }
        );

        expect(
          screen.getByText(/Commissioning is currently in progress/i)
        ).toBeInTheDocument();
      });

      it("shows a generic message if the machine has no node devices and cannot be commissioned", () => {
        const machine = factory.machineDetails({
          actions: [],
          locked: false,
          status_code: NodeStatusCode.NEW,
        });

        renderWithProviders(
          <NodeDevicesTable bus={NodeDeviceBus.PCIE} node={machine} />,
          { state }
        );

        expect(
          screen.getByText(/Commissioning cannot be run at this time/i)
        ).toBeInTheDocument();
      });

      it("shows a message if the machine has PCI devices but no USB devices", () => {
        const machine = factory.machineDetails();

        renderWithProviders(
          <NodeDevicesTable bus={NodeDeviceBus.USB} node={machine} />,
          { state }
        );

        expect(
          screen.getByText(/No USB devices discovered during commissioning./i)
        ).toBeInTheDocument();
      });

      it("only shows the header without additional commissioning information", () => {
        const controller = factory.controllerDetails();

        renderWithProviders(
          <NodeDevicesTable bus={NodeDeviceBus.USB} node={controller} />,
          { state }
        );

        expect(screen.getByText(/No USB information/i)).toBeInTheDocument();
        expect(
          screen.queryByText(/No USB devices discovered during commissioning./i)
        ).not.toBeInTheDocument();
      });
    });

    describe("displays columns correctly", () => {
      it("displays the PCI address column when bus is PCI", () => {
        renderWithProviders(
          <NodeDevicesTable bus={NodeDeviceBus.PCIE} node={machine} />,
          { state }
        );

        ["Vendor", "Product", "Driver", "NUMA node", "PCI address"].forEach(
          (column) => {
            expect(
              screen.getByRole("columnheader", {
                name: new RegExp(`^${column}`, "i"),
              })
            ).toBeInTheDocument();
          }
        );
      });

      it("displays the bus address column when bus is USB", () => {
        renderWithProviders(
          <NodeDevicesTable bus={NodeDeviceBus.USB} node={machine} />,
          { state }
        );

        ["Vendor", "Product", "Driver", "NUMA node", "Bus address"].forEach(
          (column) => {
            expect(
              screen.getByRole("columnheader", {
                name: new RegExp(`^${column}`, "i"),
              })
            ).toBeInTheDocument();
          }
        );
      });
    });

    it("can link to the machine network and storage tabs", () => {
      renderWithProviders(
        <NodeDevicesTable bus={NodeDeviceBus.PCIE} node={machine} />,
        { state }
      );

      expect(screen.getByRole("link", { name: "Network" })).toHaveAttribute(
        "href",
        urls.machines.machine.network({ id: machine.system_id })
      );
      expect(screen.getByRole("link", { name: "Storage" })).toHaveAttribute(
        "href",
        urls.machines.machine.storage({ id: machine.system_id })
      );
    });

    it("can link to the controller network and storage tabs", () => {
      state.nodedevice.items.forEach((item) => {
        item.node_id = controller.id;
      });
      renderWithProviders(
        <NodeDevicesTable bus={NodeDeviceBus.PCIE} node={controller} />,
        { state }
      );

      expect(screen.getByRole("link", { name: "Network" })).toHaveAttribute(
        "href",
        urls.controllers.controller.network({ id: controller.system_id })
      );
      expect(screen.getByRole("link", { name: "Storage" })).toHaveAttribute(
        "href",
        urls.controllers.controller.storage({ id: controller.system_id })
      );
    });

    it("displays the NUMA node index of a node device", () => {
      const numaNode = factory.machineNumaNode({ index: 128 });
      const machine = factory.machineDetails({
        numa_nodes: [numaNode, factory.machineNumaNode()],
        system_id: "abc123",
      });
      const pciDevice = factory.nodeDevice({
        bus: NodeDeviceBus.PCIE,
        id: 1,
        node_id: machine.id,
        numa_node_id: numaNode.id,
      });
      const state = factory.rootState({
        nodedevice: factory.nodeDeviceState({
          items: [pciDevice],
        }),
      });
      renderWithProviders(
        <NodeDevicesTable bus={NodeDeviceBus.PCIE} node={machine} />,
        { state }
      );

      expect(screen.getByText(numaNode.index)).toHaveClass("numa_node");
    });
  });
});
