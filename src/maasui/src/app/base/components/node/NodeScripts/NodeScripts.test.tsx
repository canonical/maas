import NodeScripts from "./NodeScripts";

import urls from "@/app/base/urls";
import { Label as CommissioningLabel } from "@/app/machines/views/MachineDetails/MachineCommissioning/MachineCommissioning";
import { Label as DeploymentLabel } from "@/app/machines/views/MachineDetails/MachineDeployment/MachineDeployment";
import { Label as TestsLabel } from "@/app/machines/views/MachineDetails/MachineTests/MachineTests";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

// Labels rendered by the pages

describe("NodeScripts", () => {
  let state: RootState;
  let machine: MachineDetails;

  beforeEach(() => {
    machine = factory.machineDetails({ system_id: "abc123" });
    state = factory.rootState({
      machine: factory.machineState({
        items: [machine],
      }),
      scriptresult: factory.scriptResultState({
        loaded: true,
      }),
    });
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
    it(`Displays: ${label} at: ${path}`, () => {
      renderWithProviders(
        <NodeScripts
          node={machine}
          urls={{
            index: urls.machines.machine.scriptsResults.index,
            commissioning: urls.machines.machine.scriptsResults.commissioning,
            deployment: urls.machines.machine.scriptsResults.deployment,
            testing: urls.machines.machine.scriptsResults.testing,
          }}
        />,
        {
          initialEntries: [path],
          state,
          pattern: `${urls.machines.machine.scriptsResults.index(null)}/*`,
        }
      );

      expect(screen.getByLabelText(label)).toBeInTheDocument();
    });
  });
});
