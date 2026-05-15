import VMWare from "../VMWare";

import { Labels as VMWareFormLabels } from "./VMWareForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
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
describe("VMWareForm", () => {
  let state: RootState;
  const configItems = [
    { name: ConfigNames.VCENTER_SERVER, value: "my server" },
    { name: ConfigNames.VCENTER_USERNAME, value: "admin" },
    { name: ConfigNames.VCENTER_PASSWORD, value: "passwd" },
    { name: ConfigNames.VCENTER_DATACENTER, value: "my datacenter" },
  ];
  beforeEach(() => {
    state = factory.rootState();
  });

  it("sets vcenter_server value", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );
    renderWithProviders(<VMWare />, { state });
    await waitForLoading();
    expect(
      screen.getByRole("textbox", { name: VMWareFormLabels.ServerLabel })
    ).toHaveValue("my server");
  });

  it("sets vcenter_username value", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );
    renderWithProviders(<VMWare />, { state });
    await waitForLoading();
    expect(
      screen.getByRole("textbox", { name: VMWareFormLabels.UsernameLabel })
    ).toHaveValue("admin");
  });

  it("sets vcenter_password value", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );
    renderWithProviders(<VMWare />, { state });
    await waitForLoading();
    const passwordInput = screen.getByLabelText(VMWareFormLabels.PasswordLabel);
    expect(passwordInput).toHaveValue("passwd");
    expect(passwordInput).toHaveAttribute("type", "password");
  });

  it("sets vcenter_datacenter value", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );
    renderWithProviders(<VMWare />, { state });
    await waitForLoading();
    expect(
      screen.getByRole("textbox", { name: VMWareFormLabels.DatacenterLabel })
    ).toHaveValue("my datacenter");
  });
});
