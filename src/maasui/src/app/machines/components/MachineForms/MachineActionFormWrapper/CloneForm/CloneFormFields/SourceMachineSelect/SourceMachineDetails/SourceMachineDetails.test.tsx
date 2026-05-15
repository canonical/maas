import SourceMachineDetails, {
  Labels as SourceMachineDetailsLabels,
} from "./SourceMachineDetails";

import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("SourceMachineDetails", () => {
  it("renders a list of the source machine's details", () => {
    const machine = factory.machineDetails({
      architecture: "",
      cpu_count: 2,
      cpu_speed: 2000,
      domain: { id: 1, name: "domain" },
      metadata: { cpu_model: "CPU model" },
      memory: 8,
      owner: "Owner",
      physical_disk_count: 2,
      pod: { id: 2, name: "pod" },
      power_type: "manual",
      status: NodeStatus.READY,
      storage: 8,
      zone: { id: 3, name: "zone" },
    });
    renderWithProviders(<SourceMachineDetails machine={machine} />);
    expect(
      screen.getByLabelText(SourceMachineDetailsLabels.Status)
    ).toHaveTextContent("Ready");
    expect(
      screen.getByLabelText(SourceMachineDetailsLabels.Cpu)
    ).toHaveTextContent("2 cores, 2 GHzCPU model");
    expect(
      screen.getByLabelText(SourceMachineDetailsLabels.Memory)
    ).toHaveTextContent("8 GiB");
    expect(
      screen.getByLabelText(SourceMachineDetailsLabels.Storage)
    ).toHaveTextContent("8 GB over 2 disks");
    expect(
      screen.getByLabelText(SourceMachineDetailsLabels.PowerType)
    ).toHaveTextContent("manual");
    expect(
      screen.getByLabelText(SourceMachineDetailsLabels.Owner)
    ).toHaveTextContent("Owner");
    expect(
      screen.getByLabelText(SourceMachineDetailsLabels.Host)
    ).toHaveTextContent("pod");
    expect(
      screen.getByLabelText(SourceMachineDetailsLabels.Zone)
    ).toHaveTextContent("zone");
    expect(
      screen.getByLabelText(SourceMachineDetailsLabels.Domain)
    ).toHaveTextContent("domain");
  });
});
