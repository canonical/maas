import { Route, Routes } from "react-router";

import ControllerLogs, { Label } from "./ControllerLogs";

import { Label as EventLogsLabel } from "@/app/base/components/node/NodeLogs/EventLogs/EventLogs";
import { Label as InstallationOutputLabel } from "@/app/base/components/node/NodeLogs/InstallationOutput/InstallationOutput";
import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("ControllerLogs", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      controller: factory.controllerState({
        items: [factory.controllerDetails({ system_id: "abc123" })],
      }),
    });
  });

  it("displays a spinner if controller is loading", () => {
    const state = factory.rootState({
      controller: factory.controllerState({
        items: [],
      }),
    });
    renderWithProviders(<ControllerLogs systemId="abc123" />, {
      state,
    });
    expect(screen.getByLabelText(Label.Loading)).toBeInTheDocument();
  });

  [
    {
      label: InstallationOutputLabel.Title,
      path: urls.controllers.controller.logs.installationOutput({
        id: "abc123",
      }),
    },
    {
      label: EventLogsLabel.Title,
      path: urls.controllers.controller.logs.index({ id: "abc123" }),
    },
    {
      label: EventLogsLabel.Title,
      path: urls.controllers.controller.logs.events({ id: "abc123" }),
    },
  ].forEach(({ label, path }) => {
    it(`Displays: ${label} at: ${path}`, async () => {
      const { router } = renderWithProviders(
        <Routes>
          <Route
            element={<ControllerLogs systemId="abc123" />}
            path={`${urls.controllers.controller.logs.index(null)}/*`}
          />
        </Routes>,
        {
          state,
          initialEntries: [`${urls.controllers.controller.logs.index(null)}/*`],
        }
      );
      await router.navigate(path);
      expect(await screen.findByLabelText(label)).toBeInTheDocument();
    });
  });
});
