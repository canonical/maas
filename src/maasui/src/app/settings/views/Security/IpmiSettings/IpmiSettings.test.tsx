import { Labels as FormFieldsLabels } from "./IpmiFormFields/IpmiFormFields";
import IpmiSettings, { Labels as IpmiSettingsLabels } from "./IpmiSettings";

import { Labels as FormikButtonLabels } from "@/app/base/components/FormikFormButtons/FormikFormButtons";
import { AutoIpmiPrivilegeLevel, ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import {
  screen,
  setupMockServer,
  mockIsPending,
  renderWithProviders,
  waitForLoading,
  waitFor,
  userEvent,
} from "@/testing/utils";

const mockServer = setupMockServer(
  configurationsResolvers.listConfigurations.handler(),
  configurationsResolvers.setBulkConfigurations.handler()
);
describe("IpmiSettings", () => {
  let initialState: RootState;

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
      value: AutoIpmiPrivilegeLevel.ADMIN,
    },
  ];

  beforeEach(() => {
    initialState = factory.rootState({
      config: factory.configState({
        loading: false,
        loaded: true,
      }),
    });
  });

  it("displays a spinner while loading", () => {
    mockIsPending();
    renderWithProviders(<IpmiSettings />, { state: initialState });
    expect(screen.getByText(IpmiSettingsLabels.Loading)).toBeInTheDocument();
  });

  it("renders the IPMI settings form", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );
    renderWithProviders(<IpmiSettings />, { state: initialState });
    await waitForLoading();
    expect(
      screen.getByRole("textbox", { name: FormFieldsLabels.IPMIUsername })
    ).toHaveValue("maas");
    expect(screen.getByLabelText(FormFieldsLabels.KGBMCKeyLabel)).toHaveValue(
      ""
    );
    expect(
      screen.getByRole("radio", {
        name: FormFieldsLabels.AdminRadio,
      })
    ).toBeChecked();
  });

  it("can update IPMI settings", async () => {
    mockServer.use(configurationsResolvers.setBulkConfigurations.handler());
    renderWithProviders(<IpmiSettings />, { state: initialState });
    await waitForLoading();
    const maasAutoIpmiKGBmcKeyInput = screen.getByLabelText(
      FormFieldsLabels.KGBMCKeyLabel
    );
    await userEvent.clear(maasAutoIpmiKGBmcKeyInput);
    await userEvent.type(maasAutoIpmiKGBmcKeyInput, "password");
    await userEvent.click(
      screen.getByRole("radio", { name: FormFieldsLabels.UserRadio })
    );
    await userEvent.click(
      screen.getByRole("button", { name: FormikButtonLabels.Submit })
    );
    await waitFor(() => {
      expect(configurationsResolvers.setBulkConfigurations.resolved).toBe(true);
    });
  });

  it("shows an error message when fetching configurations fails", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.error({
        code: 500,
        message: "Failed to fetch configurations",
      })
    );
    renderWithProviders(<IpmiSettings />, { state: initialState });
    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch configurations")
      ).toBeInTheDocument();
    });
  });

  it("shows an error message when updating configurations fails", async () => {
    mockServer.use(
      configurationsResolvers.setBulkConfigurations.error({
        code: 500,
        message: "Failed to update configurations",
      })
    );
    renderWithProviders(<IpmiSettings />, { state: initialState });
    await waitForLoading();
    await userEvent.click(
      screen.getByRole("radio", { name: FormFieldsLabels.UserRadio })
    );
    await userEvent.click(
      screen.getByRole("button", { name: FormikButtonLabels.Submit })
    );
    await waitFor(() => {
      expect(
        screen.getByText("Failed to update configurations")
      ).toBeInTheDocument();
    });
  });
});
