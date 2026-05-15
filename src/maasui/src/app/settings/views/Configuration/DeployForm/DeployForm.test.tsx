import DeployForm from "./DeployForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  within,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

describe("DeployFormFields", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        loading: false,
        loaded: true,
        items: [
          {
            name: ConfigNames.DEFAULT_OSYSTEM,
            value: "ubuntu",
            choices: [
              ["centos", "CentOS"],
              ["ubuntu", "Ubuntu"],
            ],
          },
          {
            name: ConfigNames.DEFAULT_DISTRO_SERIES,
            value: "bionic",
            choices: [
              ["precise", 'Ubuntu 12.04 LTS "Precise Pangolin"'],
              ["trusty", 'Ubuntu 14.04 LTS "Trusty Tahr"'],
              ["xenial", 'Ubuntu 16.04 LTS "Xenial Xerus"'],
              ["bionic", 'Ubuntu 18.04 LTS "Bionic Beaver"'],
            ],
          },
        ],
      }),
      general: factory.generalState({
        osInfo: factory.osInfoState({
          loaded: true,
          data: factory.osInfo({
            releases: [
              ["centos/centos66", "CentOS 6"],
              ["centos/centos70", "CentOS 7"],
              ["ubuntu/precise", "Ubuntu 12.04 LTS 'Precise Pangolin'"],
              ["ubuntu/trusty", "Ubuntu 14.04 LTS 'Trusty Tahr'"],
            ],
          }),
        }),
      }),
    });
  });

  it("displays the deploy configuration form with correct fields", () => {
    renderWithProviders(<DeployForm />, { state });

    const form = screen.getByRole("form", { name: "deploy configuration" });
    expect(form).toBeInTheDocument();

    expect(
      within(form).getByRole("combobox", {
        name: /Default operating system used for deployment/,
      })
    ).toBeInTheDocument();
    expect(
      within(form).getByRole("combobox", {
        name: /Default OS release used for deployment/,
      })
    ).toBeInTheDocument();
    expect(
      within(form).getByRole("textbox", {
        name: /Default hardware sync interval/,
      })
    ).toBeInTheDocument();
  });

  it("displays the default hardware sync interval option with a correct value", () => {
    const syncIntervalValue = "15m";
    // TODO: Investigate mutating state in integration tests https://github.com/canonical/app-tribe/issues/794
    state.config.items.push({
      name: ConfigNames.HARDWARE_SYNC_INTERVAL,
      value: syncIntervalValue,
    });

    renderWithProviders(<DeployForm />, { state });

    expect(
      screen.getByRole("textbox", { name: /Default hardware sync interval/ })
    ).toHaveValue("15");
  });

  it("adds a hardware_sync_interval field to the request on submit", async () => {
    const { store } = renderWithProviders(<DeployForm />, { state });

    await userEvent.clear(
      screen.getByRole("textbox", { name: /Default hardware sync interval/ })
    );
    await userEvent.type(
      screen.getByRole("textbox", {
        name: /Default hardware sync interval/,
      }),
      "30"
    );

    await userEvent.click(
      screen.getByRole("button", {
        name: /Save/,
      })
    );

    await waitFor(() => {
      const action = store
        .getActions()
        .find((action) => action.type === "config/update");
      expect(action.payload.params.items).toEqual(
        expect.objectContaining({
          hardware_sync_interval: "30m",
        })
      );
    });
  });

  it("displays an error message when providing an invalid hardware sync interval value", async () => {
    renderWithProviders(<DeployForm />, { state });

    const hardwareSyncInput = screen.getByRole("textbox", {
      name: /Default hardware sync interval/,
    });
    await userEvent.clear(hardwareSyncInput);
    await userEvent.type(hardwareSyncInput, "0");
    await userEvent.tab();
    await waitFor(() => {
      expect(hardwareSyncInput).toHaveAccessibleErrorMessage(
        /Hardware sync interval must be at least 1 minute/
      );
    });
  });
});
