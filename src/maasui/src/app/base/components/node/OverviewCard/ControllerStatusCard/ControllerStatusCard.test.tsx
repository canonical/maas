import ControllerStatusCard, { Labels } from "./ControllerStatusCard";

import { controllerActions } from "@/app/store/controller";
import {
  ControllerInstallType,
  ImageSyncStatus,
} from "@/app/store/controller/types";
import { NodeType } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  screen,
  userEvent,
  waitFor,
  within,
  renderWithProviders,
} from "@/testing/utils";

it("dispatches an action to poll images if controller is a rack or region+rack", () => {
  const controller = factory.controllerDetails({
    node_type: NodeType.RACK_CONTROLLER,
  });
  const state = factory.rootState({
    controller: factory.controllerState({ items: [controller] }),
  });

  const { store } = renderWithProviders(
    <ControllerStatusCard controller={controller} />,
    {
      state,
    }
  );

  expect(
    store
      .getActions()
      .some(
        (action) =>
          action.type ===
          controllerActions.pollCheckImages([controller.system_id], "").type
      )
  );
});

it("does not dispatch an action to poll images if controller is a region controller", () => {
  const controller = factory.controllerDetails({
    node_type: NodeType.REGION_CONTROLLER,
  });
  const state = factory.rootState({
    controller: factory.controllerState({ items: [controller] }),
  });

  const { store } = renderWithProviders(
    <ControllerStatusCard controller={controller} />,
    {
      state,
    }
  );

  expect(
    store
      .getActions()
      .every(
        (action) =>
          action.type !==
          controllerActions.pollCheckImages([controller.system_id], "").type
      )
  );
});

it("dispatches an action to stop polling images on unmount", () => {
  const controller = factory.controllerDetails();
  const state = factory.rootState({
    controller: factory.controllerState({ items: [controller] }),
  });

  const {
    result: { unmount },
    store,
  } = renderWithProviders(<ControllerStatusCard controller={controller} />, {
    state,
  });

  unmount();

  expect(
    store
      .getActions()
      .some(
        (action) =>
          action.type === controllerActions.pollCheckImagesStop("").type
      )
  );
});

it("renders correct version info for a deb install", async () => {
  const controller = factory.controllerDetails({
    versions: factory.controllerVersions({
      current: factory.controllerVersionInfo({ version: "1.2.3" }),
      install_type: ControllerInstallType.DEB,
      origin: "ppa:some/ppa",
    }),
  });
  const state = factory.rootState({
    controller: factory.controllerState({ items: [controller] }),
  });

  renderWithProviders(<ControllerStatusCard controller={controller} />, {
    state,
  });

  await userEvent.hover(
    screen.getByRole("button", { name: Labels.VersionDetails })
  );
  await waitFor(() => {
    expect(screen.getByLabelText(Labels.Version).textContent).toBe(
      "Version: 1.2.3"
    );
  });

  await waitFor(() => {
    expect(screen.getByLabelText(Labels.Origin).textContent).toBe(
      "Deb: ppa:some/ppa"
    );
  });
});

it("renders correct version info for a snap install", async () => {
  const controller = factory.controllerDetails({
    versions: factory.controllerVersions({
      current: factory.controllerVersionInfo({ version: "1.2.3" }),
      install_type: ControllerInstallType.SNAP,
      origin: "1.2/edge",
    }),
  });
  const state = factory.rootState({
    controller: factory.controllerState({ items: [controller] }),
  });

  renderWithProviders(<ControllerStatusCard controller={controller} />, {
    state,
  });

  await userEvent.hover(
    screen.getByRole("button", { name: Labels.VersionDetails })
  );

  await waitFor(() => {
    expect(screen.getByLabelText(Labels.Version).textContent).toBe(
      "Version: 1.2.3"
    );
  });

  await waitFor(() => {
    expect(screen.getByLabelText(Labels.Origin).textContent).toBe(
      "Channel: 1.2/edge"
    );
  });
});

it("renders correct version info for an unknown install type", async () => {
  const controller = factory.controllerDetails({
    versions: factory.controllerVersions({
      current: factory.controllerVersionInfo({ version: "" }),
      install_type: ControllerInstallType.UNKNOWN,
      origin: "nowhere",
    }),
  });
  const state = factory.rootState({
    controller: factory.controllerState({ items: [controller] }),
  });

  renderWithProviders(<ControllerStatusCard controller={controller} />, {
    state,
  });

  await userEvent.hover(
    screen.getByRole("button", { name: Labels.VersionDetails })
  );
  await waitFor(() => {
    expect(
      within(screen.getByRole("tooltip")).getByLabelText(Labels.Version)
    ).toHaveTextContent("Version: Unknown (less than 2.3.0)");
  });

  await waitFor(() => {
    expect(
      within(screen.getByRole("tooltip")).getByLabelText(Labels.Origin)
    ).toHaveTextContent("Origin: nowhere");
  });
});

it("renders OS info", () => {
  const controller = factory.controllerDetails({
    distro_series: "focal",
    osystem: "ubuntu",
  });
  const state = factory.rootState({
    controller: factory.controllerState({ items: [controller] }),
    general: factory.generalState({
      osInfo: factory.osInfoState({
        data: factory.osInfo({
          releases: [["ubuntu/focal", 'Ubuntu 20.04 LTS "Focal Fossa"']],
        }),
      }),
    }),
  });

  renderWithProviders(<ControllerStatusCard controller={controller} />, {
    state,
  });

  expect(screen.getByLabelText(Labels.OSInfo).textContent).toBe(
    'Ubuntu 20.04 LTS "Focal Fossa"'
  );
});

it("shows image sync status for rack or region+rack controllers", () => {
  const controller = factory.controllerDetails({
    node_type: NodeType.RACK_CONTROLLER,
  });
  const state = factory.rootState({
    controller: factory.controllerState({ items: [controller] }),
  });

  renderWithProviders(<ControllerStatusCard controller={controller} />, {
    state,
  });

  expect(screen.getByLabelText(Labels.ImageSyncStatus)).toBeInTheDocument();
});

it("can render when no image sync status exists", () => {
  const controller = factory.controllerDetails({
    node_type: NodeType.RACK_CONTROLLER,
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      imageSyncStatuses: factory.controllerImageSyncStatuses(),
      items: [controller],
    }),
  });

  renderWithProviders(<ControllerStatusCard controller={controller} />, {
    state,
  });

  expect(screen.getByText(Labels.NoStatus)).toBeInTheDocument();
});

it("can render when image status is synced", () => {
  const controller = factory.controllerDetails({
    node_type: NodeType.RACK_CONTROLLER,
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      imageSyncStatuses: factory.controllerImageSyncStatuses({
        [controller.system_id]: ImageSyncStatus.Synced,
      }),
      items: [controller],
    }),
  });

  renderWithProviders(<ControllerStatusCard controller={controller} />, {
    state,
  });

  expect(screen.getByLabelText(Labels.ImagesSynced)).toBeInTheDocument();
});

it("can render when checking image status", () => {
  const controller = factory.controllerDetails({
    node_type: NodeType.RACK_CONTROLLER,
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      imageSyncStatuses: factory.controllerImageSyncStatuses({
        [controller.system_id]: ImageSyncStatus.Synced,
      }),
      items: [controller],
      statuses: factory.controllerStatuses({
        [controller.system_id]: factory.controllerStatus({
          checkingImages: true,
        }),
      }),
    }),
  });

  renderWithProviders(<ControllerStatusCard controller={controller} />, {
    state,
  });

  expect(screen.getByText(Labels.CheckingImages)).toBeInTheDocument();
});

it("does not show image sync status for region controllers", () => {
  const controller = factory.controllerDetails({
    node_type: NodeType.REGION_CONTROLLER,
  });
  const state = factory.rootState({
    controller: factory.controllerState({ items: [controller] }),
  });

  renderWithProviders(<ControllerStatusCard controller={controller} />, {
    state,
  });

  expect(
    screen.queryByLabelText(Labels.ImageSyncStatus)
  ).not.toBeInTheDocument();
});
