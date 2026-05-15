import { Labels as VMWareFormLabels } from "../VMWareForm/VMWareForm";

import VMWare, { Labels as VMWareLabels } from "./VMWare";

import { ConfigNames } from "@/app/store/config/types";
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
} from "@/testing/utils";

const mockServer = setupMockServer(
  configurationsResolvers.listConfigurations.handler(),
  configurationsResolvers.setBulkConfigurations.handler()
);

describe("VMWare", () => {
  let state: RootState;
  const configItems = [
    { name: ConfigNames.VCENTER_SERVER, value: "" },
    { name: ConfigNames.VCENTER_USERNAME, value: "" },
    { name: ConfigNames.VCENTER_PASSWORD, value: "" },
    { name: ConfigNames.VCENTER_DATACENTER, value: "" },
  ];

  beforeEach(() => {
    state = factory.rootState();
  });

  it("displays a spinner if config is loading", () => {
    mockIsPending();
    renderWithProviders(<VMWare />, { state });
    expect(screen.getByText(VMWareLabels.Loading)).toBeInTheDocument();
  });

  it("displays the VMWare form if config is loaded", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );
    renderWithProviders(<VMWare />, { state });
    await waitForLoading();
    expect(
      screen.getByRole("form", { name: VMWareFormLabels.FormLabel })
    ).toBeInTheDocument();
  });
  it("shows an error message when fetching configurations fails", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.error({
        code: 500,
        message: "Failed to fetch configurations",
      })
    );

    renderWithProviders(<VMWare />, { state });

    await waitFor(() => {
      expect(
        screen.getByText("Error while fetching image configurations")
      ).toBeInTheDocument();
    });
  });
});
