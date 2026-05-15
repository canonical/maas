import { Labels as TPDFormLabels } from "../ThirdPartyDriversForm/ThirdPartyDriversForm";

import ThirdPartyDrivers, { Labels as TPDLabels } from "./ThirdPartyDrivers";

import { ConfigNames } from "@/app/store/config/types";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import {
  screen,
  setupMockServer,
  mockIsPending,
  renderWithProviders,
  waitForLoading,
} from "@/testing/utils";

setupMockServer(
  configurationsResolvers.getConfiguration.handler({
    name: ConfigNames.ENABLE_THIRD_PARTY_DRIVERS,
    value: false,
  }),
  configurationsResolvers.setConfiguration.handler()
);
describe("ThirdPartyDrivers", () => {
  it("displays a spinner if config is loading", () => {
    mockIsPending();
    renderWithProviders(<ThirdPartyDrivers />);
    expect(screen.getByText(TPDLabels.Loading)).toBeInTheDocument();
  });

  it("displays the ThirdPartyDrivers form if config is loaded", async () => {
    renderWithProviders(<ThirdPartyDrivers />);
    await waitForLoading();

    expect(
      screen.getByRole("form", { name: TPDFormLabels.FormLabel })
    ).toBeInTheDocument();
  });
});
