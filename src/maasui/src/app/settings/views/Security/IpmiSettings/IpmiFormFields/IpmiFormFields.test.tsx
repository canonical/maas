import IpmiSettings from "../IpmiSettings";

import { Labels as FormFieldsLabels } from "./IpmiFormFields";

import { AutoIpmiPrivilegeLevel, ConfigNames } from "@/app/store/config/types";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import {
  screen,
  setupMockServer,
  renderWithProviders,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  configurationsResolvers.listConfigurations.handler()
);
describe("IpmiFormFields", () => {
  const configItems = [
    {
      name: ConfigNames.MAAS_AUTO_IPMI_USER,
      value: "maas",
    },
    {
      name: ConfigNames.MAAS_AUTO_IPMI_K_G_BMC_KEY,
      value: "",
    },
    {
      name: ConfigNames.MAAS_AUTO_IPMI_USER_PRIVILEGE_LEVEL,
      value: AutoIpmiPrivilegeLevel.OPERATOR,
    },
  ];

  it("updates value for ipmi username", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );
    renderWithProviders(<IpmiSettings />);
    await waitForLoading();
    expect(
      screen.getByRole("textbox", { name: FormFieldsLabels.IPMIUsername })
    ).toHaveValue("maas");
  });

  it("updates value for ipmi user privilege level", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );
    renderWithProviders(<IpmiSettings />);
    await waitForLoading();
    expect(
      screen.getByRole("radio", { name: FormFieldsLabels.OperatorRadio })
    ).toHaveProperty("checked", true);
  });
});
