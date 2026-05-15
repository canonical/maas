import AddChassisForm from "../AddChassisForm";

import { PowerTypeNames } from "@/app/store/general/constants";
import { PowerFieldScope, PowerFieldType } from "@/app/store/general/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("AddChassisFormFields", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      domain: factory.domainState({
        items: [factory.domain({ name: "maas" })],
        loaded: true,
      }),
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          loaded: true,
        }),
      }),
    });
  });

  it("can render", () => {
    renderWithProviders(<AddChassisForm />, {
      state,
    });

    expect(
      screen.getByRole("combobox", { name: "Domain" })
    ).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "maas" })).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Power type" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save chassis" })
    ).toBeInTheDocument();
  });

  it("does not show power type fields that are scoped to nodes", async () => {
    state.general.powerTypes.data.push(
      factory.powerType({
        name: PowerTypeNames.VIRSH,
        description: "Virsh (virtual systems)",
        fields: [
          factory.powerField({
            name: "power_address",
            label: "Address",
            required: true,
            field_type: PowerFieldType.STRING,
            choices: [],
            default: "",
            scope: PowerFieldScope.BMC,
          }),
          factory.powerField({
            name: "power_pass",
            label: "Password (optional)",
            required: false,
            field_type: PowerFieldType.PASSWORD,
            choices: [],
            default: "",
            scope: PowerFieldScope.BMC,
          }),
          factory.powerField({
            name: "power_id",
            label: "Virsh VM ID",
            required: true,
            field_type: PowerFieldType.STRING,
            choices: [],
            default: "",
            scope: PowerFieldScope.NODE, // Should not show
          }),
        ],
        can_probe: true,
      })
    );

    renderWithProviders(<AddChassisForm />, {
      state,
    });

    const powerTypeSelect = screen.getByRole("combobox", {
      name: "Power type",
    });
    await userEvent.selectOptions(powerTypeSelect, PowerTypeNames.VIRSH);

    expect(screen.getByLabelText(/Address/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Virsh VM ID/i)).not.toBeInTheDocument();
  });
});
