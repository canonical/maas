import DeployForm from "../DeployForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
  setupMockServer,
} from "@/testing/utils";

const mockServer = setupMockServer(
  authResolvers.getCurrentUser.handler(),
  authResolvers.getMeStatistics.handler()
);

describe("DeployFormFields", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [
          {
            name: ConfigNames.DEFAULT_OSYSTEM,
            value: "ubuntu",
            choices: [
              ["centos", "CentOS"],
              ["ubuntu", "Ubuntu"],
            ],
          },
        ],
        errors: {},
        loaded: true,
        loading: false,
      }),
      general: factory.generalState({
        defaultMinHweKernel: {
          data: "",
          errors: {},
          loaded: true,
          loading: false,
        },
        osInfo: {
          data: {
            osystems: [
              ["centos", "CentOS"],
              ["ubuntu", "Ubuntu"],
            ],
            releases: [
              ["centos/centos66", "CentOS 6"],
              ["centos/centos70", "CentOS 7"],
              ["ubuntu/xenial", 'Ubuntu 16.04 LTS "Xenial Xerus"'],
              ["ubuntu/bionic", 'Ubuntu 18.04 LTS "Bionic Beaver"'],
              ["ubuntu/focal", 'Ubuntu 20.04 LTS "Focal Fossa"'],
            ],
            kernels: {
              ubuntu: {
                bionic: [
                  ["ga-18.04", "bionic (ga-18.04)"],
                  ["ga-18.04-lowlatency", "bionic (ga-18.04-lowlatency)"],
                  ["hwe-18.04", "bionic (hwe-18.04)"],
                  ["hwe-18.04-edge", "bionic (hwe-18.04-edge)"],
                  ["hwe-18.04-lowlatency", "bionic (hwe-18.04-lowlatency)"],
                  [
                    "hwe-18.04-lowlatency-edge",
                    "bionic (hwe-18.04-lowlatency-edge)",
                  ],
                ],
                focal: [
                  ["ga-20.04", "focal (ga-20.04)"],
                  ["ga-20.04-lowlatency", "focal (ga-20.04-lowlatency)"],
                ],
                xenial: [
                  ["ga-16.04", "xenial (ga-16.04)"],
                  ["ga-16.04-lowlatency", "xenial (ga-16.04-lowlatency)"],
                ],
              },
            },
            default_osystem: "ubuntu",
            default_release: "focal",
          },
          errors: {},
          loaded: true,
          loading: false,
        },
      }),
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machine({
            system_id: "abc123",
          }),
          factory.machine({
            system_id: "def456",
          }),
        ],
        selected: null,
        statuses: {
          abc123: factory.machineStatus(),
          def456: factory.machineStatus(),
        },
      }),
    });
  });

  it("correctly sets operating system to default", () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.default_osystem = "centos";
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, {
      state,
    });
    expect(screen.getByRole("combobox", { name: "OS" })).toHaveValue("centos");
  });

  it("correctly sets release to default", () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.default_release = "bionic";
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, { state });
    expect(screen.getByRole("combobox", { name: "Release" })).toHaveValue(
      "bionic"
    );
  });

  it("correctly sets minimum kernel to default when in default release", async () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.default_release = "bionic";
      state.general.osInfo.data.kernels.ubuntu.bionic = [
        ["ga-18.04", "bionic (ga-18.04)"],
      ];
      state.general.defaultMinHweKernel.data = "ga-18.04";
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, {
      state,
    });
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "Kernel" })).toHaveValue(
        "ga-18.04"
      );
    });
  });

  it("correctly sets minimum kernel to default when not in default release", async () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.default_release = "bionic";
      state.general.osInfo.data.kernels.ubuntu.bionic = [
        ["ga-18.04", "bionic (ga-18.04)"],
      ];
      state.general.defaultMinHweKernel.data = "different-kernel";
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, { state });
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "Kernel" })).toHaveValue("");
    });
  });

  it("disables KVM host checkbox if not Ubuntu 18.04 or 20.04", async () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.default_release = "xenial";
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, { state });
    expect(
      screen.getByRole("checkbox", { name: /Register as MAAS KVM host/ })
    ).toBeDisabled();
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Release" }),
      'Ubuntu 18.04 LTS "Bionic Beaver"'
    );

    await waitFor(() => {
      expect(
        screen.getByRole("checkbox", { name: /Register as MAAS KVM host/ })
      ).toBeEnabled();
    });
  });

  it("enables KVM host checkbox when switching to Ubuntu 18.04 from a different OS/Release", async () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.default_release = "bionic";
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, { state });
    // Initial selection is Ubuntu 18.04. Switch to CentOS 6 to CentOS 7 back to
    // Ubuntu 18.04 and checkbox should be enabled.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "OS" }),
      "CentOS"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Release" }),
      "CentOS 7"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "OS" }),
      "Ubuntu"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Release" }),
      "bionic"
    );
    await waitFor(() => {
      expect(
        screen.getByRole("checkbox", { name: /Register as MAAS KVM host/ })
      ).not.toBeDisabled();
    });
  });

  it("shows KVM host type options when the KVM host checkbox is checked", async () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.default_release = "bionic";
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, { state });
    expect(
      screen.queryByRole("radio", { name: /LXD/ })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("radio", { name: /libvirt/ })
    ).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("checkbox", { name: /Register as MAAS KVM host/ })
    );
    await waitFor(() => {
      expect(screen.getByRole("radio", { name: /LXD/ })).toBeInTheDocument();
    });
    expect(screen.getByRole("radio", { name: /libvirt/ })).toBeInTheDocument();
  });

  it("displays support message only when 'virsh' is selected for KVM host type", async () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.default_release = "bionic";
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, { state });

    const SUPPORT_MESSAGE =
      "Only Ubuntu 18.04 LTS and Ubuntu 20.04 LTS are officially supported.";

    await userEvent.click(
      screen.getByRole("checkbox", { name: /Register as MAAS KVM host/ })
    );
    await userEvent.click(screen.getByRole("radio", { name: /libvirt/ }));
    expect(screen.getByText(SUPPORT_MESSAGE)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("radio", { name: /LXD/ }));
    expect(screen.queryByText(SUPPORT_MESSAGE)).not.toBeInTheDocument();
  });

  it("displays a warning if user has no SSH keys", async () => {
    const userId = 1;
    mockServer.use(
      authResolvers.getCurrentUser.handler(factory.user({ id: userId })),
      authResolvers.getMeStatistics.handler(
        factory.userStatistics({ id: userId, sshkeys_count: 0 })
      )
    );
    renderWithProviders(<DeployForm isViewingDetails={false} />, {
      state,
    });
    await waitFor(() => {
      expect(screen.getByTestId("sshkeys-warning")).toBeInTheDocument();
    });
  });

  it(`displays an error and disables form fields if there are no OSes or
    releases to choose from`, () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.osystems = [];
      state.general.osInfo.data.releases = [];
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, {
      state,
    });
    expect(screen.getByTestId("images-error")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "OS" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Release" })).toBeDisabled();
    expect(
      screen.getByRole("checkbox", { name: /Register as MAAS KVM host/ })
    ).toBeDisabled();
  });

  it("can display the user data input", async () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.default_release = "bionic";
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, {
      state,
    });
    expect(
      screen.queryByPlaceholderText(/Paste or drop script here/)
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("checkbox", { name: /Cloud-init user-data/ })
    );
    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(/Paste or drop script here/)
      ).toBeInTheDocument();
    });
  });

  it("clears kernel selection on OS/release change when default is in different release", async () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.default_release = "bionic";
      state.general.osInfo.data.kernels.ubuntu.bionic = [
        ["ga-18.04", "bionic (ga-18.04)"],
      ];
      state.general.defaultMinHweKernel.data = "different-default-release";
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, {
      state,
    });
    // Change kernel to non-default.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Kernel" }),
      "ga-18.04"
    );
    // Change release to Ubuntu 20.04.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Release" }),
      'Ubuntu 20.04 LTS "Focal Fossa"'
    );
    // Previous kernel selection should be cleared.
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "Kernel" })).toHaveValue("");
    });
  });

  it("resets kernel selection to default on OS/release change when has same release", async () => {
    if (state.general.osInfo.data) {
      state.general.osInfo.data.default_release = "bionic";
      state.general.osInfo.data.kernels.ubuntu.bionic = [
        ["ga-18.04", "bionic (ga-18.04)"],
      ];
      state.general.defaultMinHweKernel.data = "ga-18.04";
    }
    renderWithProviders(<DeployForm isViewingDetails={false} />, {
      state,
    });
    // Change release to Ubuntu 20.04.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Release" }),
      'Ubuntu 20.04 LTS "Focal Fossa"'
    );
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "Kernel" })).toHaveValue("");
    });
    // Change release to the one that contains the default.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Release" }),
      'Ubuntu 18.04 LTS "Bionic Beaver"'
    );
    // The default kernel should now be selected.
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "Kernel" })).toHaveValue(
        "ga-18.04"
      );
    });
  });

  it("displays 'periodically sync hardware' checkbox with global setting and additional tooltip information", async () => {
    state.config.items.push({
      name: ConfigNames.HARDWARE_SYNC_INTERVAL,
      value: "15m",
    });
    renderWithProviders(<DeployForm isViewingDetails={false} />, {
      state,
    });

    expect(
      screen.getByRole("checkbox", { name: /Periodically sync hardware/ })
    ).toHaveAccessibleDescription(/Hardware sync interval: 15 minutes/);
    await userEvent.click(
      screen.getByRole("button", {
        name: /more about periodically sync hardware/i,
      })
    );
    expect(
      screen.getByRole("tooltip", {
        name: /Enable this to make MAAS periodically check the hardware/,
      })
    ).toBeInTheDocument();
  });

  it("displays a correct description text for an invalid sync interval", () => {
    state.config.items.push({
      name: ConfigNames.HARDWARE_SYNC_INTERVAL,
      value: "",
    });
    renderWithProviders(<DeployForm isViewingDetails={false} />, {
      state,
    });
    expect(
      screen.getByRole("checkbox", { name: /Periodically sync hardware/ })
    ).toHaveAccessibleDescription(/Hardware sync interval: Invalid/i);
  });

  it("'Periodically sync hardware' is unchecked by default", async () => {
    const { store } = renderWithProviders(
      <DeployForm isViewingDetails={false} />,
      {
        state,
      }
    );

    expect(
      screen.getByRole("checkbox", { name: /Periodically sync hardware/ })
    ).not.toBeChecked();
    await userEvent.click(
      screen.getByRole("button", { name: /Deploy machine/ })
    );

    await waitFor(() => {
      const action = store
        .getActions()
        .find((action) => action.type === "machine/deploy");
      expect(action?.payload?.params?.extra?.enable_hw_sync).toBeUndefined();
    });
  });

  it("adds a enable_hw_sync field to the request on submit", async () => {
    state.machine.selected = { items: [state.machine.items[0].system_id] };
    const { store } = renderWithProviders(
      <DeployForm isViewingDetails={false} />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("checkbox", { name: /Periodically sync hardware/ })
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Deploy machine/ })
    );
    await waitFor(() => {
      expect(
        screen.getByRole("checkbox", { name: /Periodically sync hardware/ })
      ).toBeChecked();
    });

    await waitFor(() => {
      const action = store
        .getActions()
        .find((action) => action.type === "machine/deploy");
      expect(action?.payload?.params?.extra?.enable_hw_sync).toEqual(true);
    });
  });

  it("selects 'Deploy to disk' as the default deployment target", () => {
    renderWithProviders(<DeployForm isViewingDetails={false} />, { state });

    expect(screen.getByRole("radio", { name: "Deploy to disk" })).toBeChecked();
    expect(
      screen.getByRole("radio", { name: "Deploy in memory" })
    ).not.toBeChecked();
  });

  it("hides 'Register as MAAS KVM host' if 'Deploy in memory' is selected", async () => {
    renderWithProviders(<DeployForm isViewingDetails={false} />, {
      state,
    });

    await userEvent.click(
      screen.getByRole("radio", { name: "Deploy in memory" })
    );

    expect(
      screen.queryByRole("checkbox", { name: "Register as MAAS KVM host" })
    ).not.toBeInTheDocument();
  });

  it("shows a tooltip for minimum OS requirements", async () => {
    renderWithProviders(<DeployForm isViewingDetails={false} />, { state });

    await userEvent.hover(
      screen.getAllByRole("button", { name: "help-mid-dark" })[1]
    );

    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent(
        "Tested with Ubuntu 24.04 LTS or higher."
      );
    });
  });

  it("shows a tooltip for minimum hardware requirements", async () => {
    renderWithProviders(<DeployForm isViewingDetails={false} />, { state });

    await userEvent.hover(
      screen.getAllByRole("button", { name: "help-mid-dark" })[0]
    );

    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent(
        ">= 4 CPU threads, >= 6GB RAM, Reserve >5x RAM size as free disk space in /var."
      );
    });
  });
});
