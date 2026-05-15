import { Label as CommissioningLabel } from "../MachineCommissioning/MachineCommissioning";
import { Label as DeploymentLabel } from "../MachineDeployment/MachineDeployment";
import { Label as TestsLabel } from "../MachineTests/MachineTests";

import MachineScripts, { Label } from "./MachineScripts";

import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("MachineScripts", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ system_id: "abc123" })],
      }),
    });
  });

  it("displays a spinner if machine is loading", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        items: [],
      }),
    });

    renderWithProviders(<MachineScripts />, {
      state,
    });

    expect(screen.getByLabelText(Label.Loading)).toBeInTheDocument();
  });

  [
    {
      label: CommissioningLabel.Title,
      path: urls.machines.machine.scriptsResults.index({ id: "abc123" }),
    },
    {
      label: CommissioningLabel.Title,
      path: urls.machines.machine.scriptsResults.commissioning.index({
        id: "abc123",
      }),
    },
    {
      label: TestsLabel.Title,
      path: urls.machines.machine.scriptsResults.testing.index({
        id: "abc123",
      }),
    },
    {
      label: DeploymentLabel.Title,
      path: urls.machines.machine.scriptsResults.deployment.index({
        id: "abc123",
      }),
    },
  ].forEach(({ label, path }) => {
    it(`displays: ${label} at: ${path}`, () => {
      renderWithProviders(<MachineScripts />, {
        initialEntries: [path],
        state,
        pattern: `${urls.machines.machine.scriptsResults.index(null)}/*`,
      });
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    });
  });
});
