import StorageForm from "./StorageForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import {
  userEvent,
  screen,
  waitFor,
  setupMockServer,
  renderWithProviders,
  mockIsPending,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  configurationsResolvers.listConfigurations.handler(),
  configurationsResolvers.setBulkConfigurations.handler()
);

describe("StorageForm", () => {
  let state: RootState;

  const configItems = [
    {
      name: ConfigNames.ENABLE_DISK_ERASING_ON_RELEASE,
      value: true,
    },
    {
      name: ConfigNames.DISK_ERASE_WITH_SECURE_ERASE,
      value: true,
    },
    {
      name: ConfigNames.DISK_ERASE_WITH_QUICK_ERASE,
      value: true,
    },
    {
      name: ConfigNames.DEFAULT_STORAGE_LAYOUT,
      value: "flat",
    },
  ];
  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        loaded: true,
        items: [
          {
            name: ConfigNames.DEFAULT_STORAGE_LAYOUT,
            value: "flat",
            choices: [
              ["bcache", "Bcache layout"],
              ["blank", "No storage (blank) layout"],
              ["flat", "Flat layout"],
              ["lvm", "LVM layout"],
              ["vmfs6", "VMFS6 layout"],
            ],
          },
        ],
      }),
    });
  });

  it("renders the storage form", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({
        items: configItems,
      })
    );
    renderWithProviders(<StorageForm />, { state });
    await waitForLoading();
    expect(
      screen.getByRole("combobox", { name: "Default storage layout" })
    ).toHaveValue("flat");
    expect(
      screen.getByRole("checkbox", {
        name: "Erase nodes' disks prior to releasing",
      })
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", {
        name: "Use secure erase by default when erasing disks",
      })
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", {
        name: "Use quick erase by default when erasing disks",
      })
    ).toBeChecked();
  });
  it("can update storage configuration", async () => {
    renderWithProviders(<StorageForm />, { state });
    await waitForLoading();
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Default storage layout" }),
      "Bcache layout"
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(configurationsResolvers.setBulkConfigurations.resolved).toBe(true);
    });
  });

  it("shows a spinner while loading", async () => {
    mockIsPending();
    renderWithProviders(<StorageForm />, { state });

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("shows an error message when fetching configurations fails", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.error({
        code: 500,
        message: "Failed to fetch configurations",
      })
    );

    renderWithProviders(<StorageForm />, { state });

    await waitFor(() => {
      expect(
        screen.getByText("Error while fetching storage configurations")
      ).toBeInTheDocument();
    });
  });

  it("shows an error message when saving configurations fails", async () => {
    mockServer.use(
      configurationsResolvers.setBulkConfigurations.error({
        code: 500,
        message: "Failed to save configurations",
      })
    );

    renderWithProviders(<StorageForm />, { state });
    await waitForLoading();
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Default storage layout" }),
      "Bcache layout"
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to save configurations")
      ).toBeInTheDocument();
    });
  });
});
