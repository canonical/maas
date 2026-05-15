import { StatusColumn } from "./StatusColumn";

import { ControllerVersionIssues } from "@/app/store/controller/types";
import type { RootState } from "@/app/store/root/types";
import { ServiceStatus } from "@/app/store/service/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("StatusColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      controller: factory.controllerState({
        loaded: true,
        items: [
          factory.controller({
            system_id: "abc123",
            service_ids: [1, 2],
          }),
        ],
      }),
      service: factory.serviceState({
        items: [
          factory.service({
            id: 1,
            status: ServiceStatus.RUNNING,
          }),
          factory.service({
            id: 2,
            status: ServiceStatus.RUNNING,
          }),
        ],
      }),
    });
  });

  it("displays a warning if there is a version error", () => {
    state.controller.items[0].versions = factory.controllerVersions({
      issues: [ControllerVersionIssues.DIFFERENT_CHANNEL],
    });
    renderWithProviders(
      <StatusColumn controller={state.controller.items[0]} />,
      {
        initialEntries: ["/controllers"],
        state,
      }
    );
    expect(screen.getByTestId("version-error")).toBeInTheDocument();
  });

  it("displays the controller status if there are no errors", async () => {
    renderWithProviders(
      <StatusColumn controller={state.controller.items[0]} />,
      {
        initialEntries: ["/controllers"],
        state,
      }
    );

    await userEvent.click(screen.getByRole("button", { name: /success/i }));
    expect(screen.getByRole("tooltip")).toHaveTextContent("2 running");
    expect(screen.getByTestId("controller-status-icon")).toHaveClass(
      "p-icon--success"
    );
  });
});
