import * as reduxToolkit from "@reduxjs/toolkit";

import { Labels } from "./DhcpFormFields";

import DhcpForm from "@/app/base/components/DhcpForm";
import { getIpRangeDisplayName } from "@/app/store/iprange/utils";
import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  within,
  renderWithProviders,
} from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

const machines = [factory.machine()];
const ipRange = factory.ipRange();
const callId = "mocked-nanoid";

describe("DhcpFormFields", () => {
  let state: RootState;

  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValue(callId);
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue(callId);
    state = factory.rootState({
      controller: factory.controllerState({ loaded: true }),
      device: factory.deviceState({ loaded: true }),
      dhcpsnippet: factory.dhcpSnippetState({
        items: [
          factory.dhcpSnippet({
            created: factory.timestamp("Thu, 15 Aug. 2019 06:21:39"),
            id: 1,
            name: "lease",
            updated: factory.timestamp("Thu, 15 Aug. 2019 06:21:39"),
            value: "lease 10",
          }),
          factory.dhcpSnippet({
            created: factory.timestamp("Thu, 15 Aug. 2019 06:21:39"),
            id: 2,
            name: "class",
            updated: factory.timestamp("Thu, 15 Aug. 2019 06:21:39"),
          }),
        ],
        loaded: true,
      }),
      machine: factory.machineState({
        items: machines,
        lists: {
          [callId]: factory.machineStateList({
            loading: false,
            loaded: true,
            groups: [
              factory.machineStateListGroup({
                items: [machines[0].system_id],
                name: "Deployed",
              }),
            ],
          }),
        },
        loaded: true,
      }),
      subnet: factory.subnetState({
        items: [
          factory.subnet({
            id: 1,
            name: "test.local",
          }),
        ],
        loaded: true,
      }),
      iprange: factory.ipRangeState({
        items: [ipRange],
        loaded: true,
      }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a notification if editing and disabled", () => {
    renderWithProviders(
      <DhcpForm
        analyticsCategory="settings"
        id={state.dhcpsnippet.items[0].id}
      />,
      { state }
    );

    expect(screen.getByText(Labels.Disabled)).toBeInTheDocument();
  });

  it("shows a loader if the models have not loaded", async () => {
    state.subnet.loading = true;
    state.device.loading = true;
    state.controller.loading = true;
    state.machine.loading = true;
    state.subnet.loaded = false;
    state.device.loaded = false;
    state.controller.loaded = false;
    state.machine.loaded = false;

    renderWithProviders(<DhcpForm analyticsCategory="settings" />, { state });
    const select = screen.getByRole("combobox", { name: Labels.Type });

    await userEvent.selectOptions(select, "subnet");

    expect(
      screen.getByRole("alert", { name: Labels.LoadingData })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: Labels.AppliesTo })
    ).not.toBeInTheDocument();
  });

  it("shows the entity options for a chosen type", async () => {
    renderWithProviders(<DhcpForm analyticsCategory="settings" />, { state });
    const select = screen.getByRole("combobox", { name: Labels.Type });

    await userEvent.selectOptions(select, "subnet");

    expect(
      screen.queryByRole("alert", { name: Labels.LoadingData })
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: Labels.AppliesTo })
    ).toBeInTheDocument();
  });

  it("allows to select an IP Range", async () => {
    renderWithProviders(<DhcpForm analyticsCategory="settings" />, { state });
    const select = screen.getByRole("combobox", { name: Labels.Type });

    await userEvent.selectOptions(select, "iprange");

    expect(
      screen.queryByRole("alert", { name: Labels.LoadingData })
    ).not.toBeInTheDocument();
    await userEvent.selectOptions(
      screen.getByRole("combobox", {
        name: Labels.AppliesTo,
      }),
      getIpRangeDisplayName(ipRange)
    );
  });

  it("resets the entity if the type changes", async () => {
    const machine = state.machine.items[0];

    renderWithProviders(<DhcpForm analyticsCategory="settings" />, { state });
    // Set an initial type.
    const typeSelect = screen.getByRole("combobox", { name: Labels.Type });
    await userEvent.selectOptions(typeSelect, "subnet");
    await userEvent.selectOptions(
      screen.getByRole("combobox", {
        name: Labels.AppliesTo,
      }),
      "test.local"
    );
    // Select a machine. Value should get set.
    await userEvent.selectOptions(typeSelect, "machine");
    await userEvent.click(
      screen.getByRole("button", { name: /Choose machine/ })
    );
    await waitFor(() => {
      expect(screen.getByRole("grid")).toHaveAttribute("aria-busy", "false");
    });
    await userEvent.click(
      within(screen.getByRole("grid")).getByText(machine.hostname)
    );
    expect(
      screen.getByRole("button", { name: new RegExp(machine.hostname, "i") })
    ).toHaveAccessibleDescription(Labels.AppliesTo);
    // Change the type. The select value should be cleared.
    await userEvent.selectOptions(typeSelect, "subnet");
    expect(
      screen.getByRole("combobox", {
        name: Labels.AppliesTo,
      })
    ).toHaveValue("");
  });
});
