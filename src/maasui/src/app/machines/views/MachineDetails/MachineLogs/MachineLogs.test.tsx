import MachineLogs, { Label } from "./MachineLogs";

import { Label as EventLogsLabel } from "@/app/base/components/node/NodeLogs/EventLogs/EventLogs";
import { Label as InstallationOutputLabel } from "@/app/base/components/node/NodeLogs/InstallationOutput/InstallationOutput";
import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("MachineLogs", () => {
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
    renderWithProviders(<MachineLogs />, {
      state,
    });
    expect(screen.getByLabelText(Label.Loading)).toBeInTheDocument();
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
      renderWithProviders(<MachineLogs />, {
        initialEntries: [path],
        state,
        pattern: `${urls.machines.machine.logs.index(null)}/*`,
      });
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    });
  });
});
