import { Label as EventLogsLabel } from "./EventLogs/EventLogs";
import { Label as InstallationOutputLabel } from "./InstallationOutput/InstallationOutput";
import NodeLogs from "./NodeLogs";

import urls from "@/app/base/urls";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("NodeLogs", () => {
  let state: RootState;
  let machine: MachineDetails;

  beforeEach(() => {
    machine = factory.machineDetails({ system_id: "abc123" });
    state = factory.rootState({
      machine: factory.machineState({
        items: [machine],
      }),
    });
  });

  [
    {
      label: InstallationOutputLabel.Title,
      path: urls.machines.machine.logs.installationOutput({ id: "abc123" }),
    },
    {
      label: EventLogsLabel.Title,
      path: urls.machines.machine.logs.index({ id: "abc123" }),
    },
    {
      label: EventLogsLabel.Title,
      path: urls.machines.machine.logs.events({ id: "abc123" }),
    },
  ].forEach(({ label, path }) => {
    it(`Displays: ${label} at: ${path}`, () => {
      renderWithProviders(
        <NodeLogs
          node={machine}
          urls={{
            events: urls.machines.machine.logs.events,
            index: urls.machines.machine.logs.index,
            installationOutput: urls.machines.machine.logs.installationOutput,
          }}
        />,
        {
          initialEntries: [path],
          state,
          pattern: `${urls.machines.machine.logs.index(null)}/*`,
        }
      );
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    });
  });
});
