import PowerForm from "./PowerForm";

import { Labels } from "@/app/base/components/EditableSection";
import { PowerTypeNames } from "@/app/store/general/constants";
import { PowerFieldScope, PowerFieldType } from "@/app/store/general/types";
import { machineActions } from "@/app/store/machine";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

let state: RootState;
beforeEach(() => {
  state = factory.rootState({
    general: factory.generalState({
      powerTypes: factory.powerTypesState({
        data: [
          factory.powerType({
            fields: [
              factory.powerField({
                name: "amt-field",
                label: "AMT field",
                field_type: PowerFieldType.STRING,
                scope: PowerFieldScope.NODE,
              }),
            ],
            name: PowerTypeNames.AMT,
          }),
          factory.powerType({
            fields: [
              factory.powerField({
                name: "apc-field",
                label: "APC field",
                field_type: PowerFieldType.STRING,
                scope: PowerFieldScope.NODE,
              }),
            ],
            name: PowerTypeNames.APC,
          }),
          factory.powerType({
            fields: [
              factory.powerField({
                name: "ip_address",
                label: "IP address",
                field_type: PowerFieldType.IP_ADDRESS,
                scope: PowerFieldScope.NODE,
              }),
            ],
            name: PowerTypeNames.IPMI,
          }),
        ],
        loaded: true,
      }),
    }),
    machine: factory.machineState({
      items: [
        factory.machineDetails({
          permissions: ["edit"],
          power_type: PowerTypeNames.AMT,
          system_id: "abc123",
        }),
        factory.machineDetails({
          permissions: ["edit"],
          power_type: PowerTypeNames.IPMI,
          system_id: "def456",
        }),
      ],
      statuses: factory.machineStatuses({
        abc123: factory.machineStatus(),
        def456: factory.machineStatus(),
      }),
    }),
  });
});

it("is not editable if machine does not have edit permission", () => {
  state.machine.items[0].permissions = [];

  renderWithProviders(<PowerForm systemId="abc123" />, { state });

  expect(
    screen.queryByRole("button", { name: Labels.EditButton })
  ).not.toBeInTheDocument();
});

it("is editable if machine has edit permission", () => {
  state.machine.items[0].permissions = ["edit"];

  renderWithProviders(<PowerForm systemId="abc123" />, { state });

  expect(
    screen.getAllByRole("button", { name: Labels.EditButton }).length
  ).not.toBe(0);
});

it("renders read-only text fields until edit button is pressed", async () => {
  renderWithProviders(<PowerForm systemId="abc123" />, { state });

  expect(
    screen.queryByRole("combobox", { name: "Power type" })
  ).not.toBeInTheDocument();

  await userEvent.click(
    screen.getAllByRole("button", { name: Labels.EditButton })[0]
  );

  expect(
    screen.getByRole("combobox", { name: "Power type" })
  ).toBeInTheDocument();
});

it("can validate IPv6 addresses with a port for IPMI power type", async () => {
  renderWithProviders(<PowerForm systemId="def456" />, { state });

  await userEvent.click(
    screen.getAllByRole("button", { name: Labels.EditButton })[0]
  );

  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Power type" }),
    PowerTypeNames.IPMI
  );

  await userEvent.clear(screen.getByRole("textbox", { name: "IP address" }));
  await userEvent.type(
    screen.getByRole("textbox", { name: "IP address" }),
    "not an ip address"
  );

  await userEvent.tab();

  expect(
    screen.getByText("Please enter a valid IP address.")
  ).toBeInTheDocument();

  await userEvent.clear(screen.getByRole("textbox", { name: "IP address" }));
  await userEvent.type(
    screen.getByRole("textbox", { name: "IP address" }),
    // This is entered as [2001:db8::1]:8080, since square brackets are
    // special characters in testing-library user events and can be escaped by doubling.
    "[[2001:db8::1]:8080"
  );

  await userEvent.tab();

  expect(
    screen.queryByText("Please enter a valid IP address.")
  ).not.toBeInTheDocument();
});

it("can validate IPv4 addresses with a port for IPMI power type", async () => {
  renderWithProviders(<PowerForm systemId="def456" />, { state });

  await userEvent.click(
    screen.getAllByRole("button", { name: Labels.EditButton })[0]
  );

  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Power type" }),
    PowerTypeNames.IPMI
  );

  await userEvent.clear(screen.getByRole("textbox", { name: "IP address" }));
  await userEvent.type(
    screen.getByRole("textbox", { name: "IP address" }),
    "not an ip address"
  );

  await userEvent.tab();

  expect(
    screen.getByText("Please enter a valid IP address.")
  ).toBeInTheDocument();

  await userEvent.clear(screen.getByRole("textbox", { name: "IP address" }));
  await userEvent.type(
    screen.getByRole("textbox", { name: "IP address" }),
    "192.168.0.2:8080"
  );

  await userEvent.tab();

  expect(
    screen.queryByText("Please enter a valid IP address.")
  ).not.toBeInTheDocument();
});
it("correctly dispatches an action to update a machine's power", async () => {
  const machine = factory.machineDetails({
    permissions: ["edit"],
    pod: undefined,
    power_type: PowerTypeNames.AMT,
    system_id: "abc123",
  });
  state.machine.items = [machine];

  const { store } = renderWithProviders(<PowerForm systemId="abc123" />, {
    state,
  });

  await userEvent.click(
    screen.getAllByRole("button", { name: Labels.EditButton })[0]
  );
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Power type" }),
    PowerTypeNames.APC
  );
  await userEvent.clear(screen.getByRole("textbox", { name: "APC field" }));
  await userEvent.type(
    screen.getByRole("textbox", { name: "APC field" }),
    "abcde"
  );
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

  const expectedAction = machineActions.update({
    extra_macs: machine.extra_macs,
    power_parameters: {
      "apc-field": "abcde",
    },
    power_type: PowerTypeNames.APC,
    pxe_mac: machine.pxe_mac,
    system_id: machine.system_id,
  });
  const actualActions = store.getActions();
  await waitFor(() => {
    expect(
      actualActions.find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });
});
