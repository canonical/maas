import AddChassisForm from "./AddChassisForm";

import { PowerTypeNames } from "@/app/store/general/constants";
import {
  DriverType,
  PowerFieldScope,
  PowerFieldType,
} from "@/app/store/general/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("AddChassisForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      domain: factory.domainState({
        items: [
          factory.domain({
            name: "maas",
          }),
        ],
        loaded: true,
      }),
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          data: [
            factory.powerType({
              name: "manual",
              description: "Manual",
              fields: [],
              can_probe: false,
            }),
            factory.powerType({
              name: PowerTypeNames.WEDGE,
              description: "Dummy power type",
              fields: [
                factory.powerField({
                  name: "power_address",
                  label: "IP address",
                  required: true,
                  field_type: PowerFieldType.STRING,
                  choices: [],
                  default: "",
                  scope: PowerFieldScope.BMC,
                }),
              ],
              can_probe: true,
            }),
            factory.powerType({
              driver_type: DriverType.POWER,
              name: "vmware",
              description: "VMware",
              fields: [
                factory.powerField({
                  name: "power_vm_name",
                  label: "VM Name (if UUID unknown)",
                  required: false,
                  field_type: PowerFieldType.STRING,
                  choices: [],
                  default: "",
                  scope: PowerFieldScope.NODE,
                }),
                factory.powerField({
                  name: "power_uuid",
                  label: "VM UUID (if known)",
                  required: false,
                  field_type: PowerFieldType.STRING,
                  choices: [],
                  default: "",
                  scope: PowerFieldScope.NODE,
                }),
                factory.powerField({
                  name: "power_address",
                  label: "VMware IP",
                  required: true,
                  field_type: PowerFieldType.STRING,
                  choices: [],
                  default: "",
                  scope: PowerFieldScope.BMC,
                }),
                factory.powerField({
                  name: "power_user",
                  label: "VMware username",
                  required: true,
                  field_type: PowerFieldType.STRING,
                  choices: [],
                  default: "",
                  scope: PowerFieldScope.BMC,
                }),
                factory.powerField({
                  name: "power_pass",
                  label: "VMware password",
                  required: true,
                  field_type: PowerFieldType.PASSWORD,
                  choices: [],
                  default: "",
                  scope: PowerFieldScope.BMC,
                }),
                factory.powerField({
                  name: "power_port",
                  label: "VMware API port (optional)",
                  required: false,
                  field_type: PowerFieldType.STRING,
                  choices: [],
                  default: "",
                  scope: PowerFieldScope.BMC,
                }),
                factory.powerField({
                  name: "power_protocol",
                  label: "VMware API protocol (optional)",
                  required: false,
                  field_type: PowerFieldType.STRING,
                  choices: [],
                  default: "",
                  scope: PowerFieldScope.BMC,
                }),
              ],
              missing_packages: [],
              can_probe: true,
              queryable: true,
            }),
          ],
          loaded: true,
        }),
      }),
    });
  });

  it("fetches the necessary data on load if not already loaded", () => {
    state.domain.loaded = false;
    const { store } = renderWithProviders(<AddChassisForm />, {
      state,
    });
    const expectedActions = ["FETCH_DOMAIN", "general/fetchPowerTypes"];
    const actions = store.getActions();
    expectedActions.forEach((expectedAction) => {
      expect(actions.some((action) => action.type === expectedAction));
    });
  });

  it("displays a spinner if data has not loaded", () => {
    state.domain.loaded = false;
    state.general.powerTypes.loaded = false;
    renderWithProviders(<AddChassisForm />, {
      state,
    });
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("correctly dispatches action to add chassis", async () => {
    const { store } = renderWithProviders(<AddChassisForm />, {
      state,
    });

    // Select vmware from power types dropdown
    await userEvent.selectOptions(
      screen.getByLabelText("Power type"),
      "vmware"
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: "VMware IP" }),
      "192.168.1.1"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "VMware username" }),
      "user1"
    );
    await userEvent.type(screen.getByLabelText("VMware password"), "secret");
    await userEvent.type(
      screen.getByRole("textbox", { name: "VMware API port (optional)" }),
      "8000"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "VMware API protocol (optional)" }),
      "abc123"
    );

    await userEvent.click(screen.getByRole("button", { name: "Save chassis" }));

    expect(
      store.getActions().find((action) => action.type === "machine/addChassis")
    ).toStrictEqual({
      type: "machine/addChassis",
      payload: {
        params: {
          chassis_type: "vmware",
          domain: "maas",
          hostname: "192.168.1.1",
          password: "secret",
          port: "8000",
          protocol: "abc123",
          username: "user1",
        },
      },
    });
  });
});
