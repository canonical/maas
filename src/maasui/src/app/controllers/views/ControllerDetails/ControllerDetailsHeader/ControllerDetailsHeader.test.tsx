import ControllerDetailsHeader from "./ControllerDetailsHeader";

import type { ControllerActions } from "@/app/store/controller/types";
import { NodeActions } from "@/app/store/types/node";
import { getNodeActionTitle } from "@/app/store/utils";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

it("displays a spinner as the title if controller has not loaded yet", () => {
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [],
    }),
  });

  renderWithProviders(<ControllerDetailsHeader systemId="abc123" />, { state });

  expect(
    screen.getByTestId("section-header-title-spinner")
  ).toBeInTheDocument();
});

it("displays a spinner as the subtitle if loaded controller is not the detailed type", () => {
  const controller = factory.controller();
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
  });

  renderWithProviders(
    <ControllerDetailsHeader systemId={controller.system_id} />,
    { state }
  );

  expect(
    screen.getByTestId("section-header-subtitle-spinner")
  ).toBeInTheDocument();
});

it("displays the controller's FQDN once loaded and detailed type", () => {
  const controllerDetails = factory.controllerDetails();
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controllerDetails],
    }),
  });

  renderWithProviders(
    <ControllerDetailsHeader systemId={controllerDetails.system_id} />,
    { state }
  );

  expect(
    screen.getByRole("heading", { name: controllerDetails.fqdn })
  ).toBeInTheDocument();
});

it("displays actions in take action menu", async () => {
  const actions: ControllerActions[] = [
    NodeActions.SET_ZONE,
    NodeActions.IMPORT_IMAGES,
    NodeActions.DELETE,
  ];
  const controllerDetails = factory.controllerDetails({
    actions,
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controllerDetails],
    }),
  });

  renderWithProviders(
    <ControllerDetailsHeader systemId={controllerDetails.system_id} />,
    { state }
  );

  const actionLabels = actions.map(getNodeActionTitle);

  actionLabels.forEach((name) => {
    expect(
      screen.queryByRole("button", { name: new RegExp(name) })
    ).not.toBeInTheDocument();
  });

  await userEvent.click(screen.getByRole("button", { name: "Take action" }));

  actionLabels.forEach((name) => {
    expect(
      screen.getByRole("button", { name: new RegExp(name) })
    ).toBeInTheDocument();
  });
});
