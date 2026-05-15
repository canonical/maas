import AddMachineForm from "../AddMachineForm";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

setupMockServer(
  zoneResolvers.listZones.handler(),
  poolsResolvers.listPools.handler()
);

describe("AddMachineFormFields", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      domain: factory.domainState({
        items: [factory.domain()],
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
              description: "Manual",
              fields: [],
            }),
            factory.powerType({
              name: "ipmi",
              description: "IPMI",
            }),
          ],
          loaded: true,
        }),
      }),
    });
  });

  const renderAddMachineFormFields = async () => {
    renderWithProviders(<AddMachineForm />, {
      initialEntries: ["/machines/add"],
      state,
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });
  };

  it("correctly sets minimum kernel to default", async () => {
    state.general.defaultMinHweKernel.data = "ga-18.04";
    await renderAddMachineFormFields();

    await waitFor(() => {
      expect(
        screen.getByRole("option", {
          name: "bionic (ga-18.04)",
          selected: true,
        })
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole("option", {
        name: "xenial (ga-16.04)",
        selected: false,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", {
        name: "No minimum kernel",
        selected: false,
      })
    ).toBeInTheDocument();
  });

  it("can add extra mac address fields", async () => {
    await renderAddMachineFormFields();

    expect(
      screen.queryByRole("textbox", { name: "Extra MAC address 1" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: "Extra MAC address 2" })
    ).not.toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Add MAC address" })
      ).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Add MAC address" })
    );

    expect(
      screen.getByRole("textbox", { name: "Extra MAC address 1" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: "Extra MAC address 2" })
    ).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Add MAC address" })
    );

    expect(
      screen.getByRole("textbox", { name: "Extra MAC address 1" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: "Extra MAC address 2" })
    ).toBeInTheDocument();
  });

  it("can remove extra mac address fields", async () => {
    await renderAddMachineFormFields();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Add MAC address" })
      ).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Add MAC address" })
    );

    expect(screen.getByTestId("extra-macs-0")).toBeInTheDocument();

    await userEvent.click(
      within(screen.getByTestId("extra-macs-0")).getByRole("button")
    );

    expect(screen.queryByTestId("extra-macs-0")).not.toBeInTheDocument();
  });

  it("does not require MAC address field if power_type is 'ipmi'", async () => {
    await renderAddMachineFormFields();

    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: "MAC address" })
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("textbox", { name: "MAC address" })).toBeRequired();

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Power type" }),
      "ipmi"
    );

    expect(
      screen.getByRole("textbox", { name: "MAC address" })
    ).not.toBeRequired();
  });
});
