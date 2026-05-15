import AddMachineForm from "./AddMachineForm";

import { PowerFieldType } from "@/app/store/general/types";
import { machineActions } from "@/app/store/machine";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
  setupMockServer,
} from "@/testing/utils";

setupMockServer(
  poolsResolvers.listPools.handler(),
  zoneResolvers.listZones.handler()
);

describe("AddMachineForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      domain: factory.domainState({
        items: [factory.domain({ name: "maas" })],
        loaded: true,
      }),
      general: factory.generalState({
        architectures: factory.architecturesState({
          data: ["amd64/generic"],
          loaded: true,
        }),
        defaultMinHweKernel: factory.defaultMinHweKernelState({
          data: "ga-16.04",
          loaded: true,
        }),
        hweKernels: factory.hweKernelsState({
          data: [
            ["ga-16.04", "xenial (ga-16.04)"],
            ["ga-18.04", "bionic (ga-18.04)"],
          ],
          loaded: true,
        }),
        powerTypes: factory.powerTypesState({
          data: [
            factory.powerType({
              name: "manual",
              fields: [],
            }),
            factory.powerType({
              name: "amt",
              fields: [
                factory.powerField({
                  name: "power_address",
                  label: "IP address",
                  field_type: PowerFieldType.STRING,
                }),
              ],
            }),
            factory.powerType({
              name: "apc",
              fields: [
                factory.powerField({
                  name: "power_id",
                  label: "Power ID",
                  field_type: PowerFieldType.STRING,
                }),
              ],
            }),
          ],
          loaded: true,
        }),
      }),
    });
  });

  it("fetches the necessary data on load if not already loaded", () => {
    const { store } = renderWithProviders(<AddMachineForm />, {
      state,
    });
    const expectedActions = [
      "FETCH_DOMAIN",
      "general/fetchArchitectures",
      "general/fetchDefaultMinHweKernel",
      "general/fetchHweKernels",
      "general/fetchPowerTypes",
      "resourcepool/fetch",
      "zone/fetch",
    ];
    const actions = store.getActions();
    expectedActions.forEach((expectedAction) => {
      expect(actions.some((action) => action.type === expectedAction));
    });
  });

  it("displays a spinner if data has not loaded", () => {
    renderWithProviders(<AddMachineForm />, {
      state,
    });
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("enables submit when a power type with no fields is chosen", async () => {
    renderWithProviders(<AddMachineForm />, {
      state,
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });
    // Choose the "manual" power type which has no power fields, and fill in other
    // required fields.
    await waitFor(() => {
      expect(screen.queryByTestId(/Loading/)).not.toBeInTheDocument();
    });
    await userEvent.selectOptions(
      await screen.findByRole("combobox", { name: "Power type" }),
      "manual"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "MAC address" }),
      "11:11:11:11:11:11"
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Save machine" })
      ).toBeEnabled();
    });
  });

  it("can handle saving a machine", async () => {
    const { store } = renderWithProviders(<AddMachineForm />, {
      state,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: "Machine name" })
      ).toBeInTheDocument();
    });

    await userEvent.type(
      screen.getByRole("textbox", { name: "Machine name" }),
      "mean-bean"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Domain" }),
      "maas"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Architecture" }),
      "amd64/generic"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Minimum kernel" }),
      "ga-16.04"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Zone" }),
      "zone-1"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Resource pool" }),
      "swimming"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "MAC address" }),
      "11:11:11:11:11:11"
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: /Register as DPU/i })
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Power type" }),
      "manual"
    );
    await userEvent.click(screen.getByRole("button", { name: "Save machine" }));

    const expectedAction = machineActions.create({
      architecture: "amd64/generic",
      domain: { name: "maas" },
      extra_macs: [],
      hostname: "mean-bean",
      is_dpu: true,
      min_hwe_kernel: "ga-16.04",
      pool: { name: "swimming" },
      power_parameters: {},
      power_type: "manual",
      pxe_mac: "11:11:11:11:11:11",
      zone: { name: "1" },
    });
    await waitFor(() => {
      expect(
        store.getActions().find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });
  });

  it("correctly trims power parameters before dispatching action", async () => {
    const { store } = renderWithProviders(<AddMachineForm />, {
      state,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: "MAC address" })
      ).toBeInTheDocument();
    });

    // Choose initial power type and fill in fields.
    await userEvent.type(
      screen.getByRole("textbox", { name: "MAC address" }),
      "11:11:11:11:11:11"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Power type" }),
      "amt"
    );
    const amtField = screen.getByRole("textbox", { name: "IP address" });
    await userEvent.type(amtField, "192.168.1.1");

    // Change power type and fill in new fields.
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Power type" }),
      "apc"
    );
    const apcField = screen.getByRole("textbox", { name: "Power ID" });
    await userEvent.clear(apcField);
    await userEvent.type(apcField, "12345");
    await userEvent.click(screen.getByRole("button", { name: "Save machine" }));

    const expectedAction = machineActions.create({
      architecture: "amd64/generic",
      domain: { name: "maas" },
      extra_macs: [],
      hostname: "",
      is_dpu: false,
      min_hwe_kernel: "ga-16.04",
      pool: { name: "swimming" },
      // Create action should not include power_address parameter since it does
      // not exist for the currently selected power type.
      power_parameters: {
        power_id: "12345",
      },
      power_type: "apc",
      pxe_mac: "11:11:11:11:11:11",
      zone: { name: "zone-1" },
    });
    await waitFor(() => {
      expect(
        store.getActions().find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });
  });

  it("correctly filters empty extra mac fields", async () => {
    const { store } = renderWithProviders(<AddMachineForm />, {
      state,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("combobox", { name: "Power type" })
      ).toBeInTheDocument();
    });

    // Submit the form with two extra macs, where one is an empty string
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Power type" }),
      "manual"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "MAC address" }),
      "11:11:11:11:11:11"
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Add MAC address" })
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Add MAC address" })
    );
    await userEvent.type(
      screen.getByLabelText("Extra MAC address 1"),
      "22:22:22:22:22:22"
    );
    await userEvent.clear(screen.getByLabelText("Extra MAC address 2"));
    await userEvent.click(screen.getByRole("button", { name: "Save machine" }));

    const expectedAction = machineActions.create({
      architecture: "amd64/generic",
      domain: { name: "maas" },
      // There should only be one extra MAC defined.
      extra_macs: ["22:22:22:22:22:22"],
      is_dpu: false,
      hostname: "",
      min_hwe_kernel: "ga-16.04",
      pool: { name: "swimming" },
      power_parameters: {},
      power_type: "manual",
      pxe_mac: "11:11:11:11:11:11",
      zone: { name: "zone-1" },
    });
    await waitFor(() => {
      expect(
        store.getActions().find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });
  });
});
