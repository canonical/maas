import ThirdPartyDriversForm, {
  Labels as TPDFormLabels,
} from "./ThirdPartyDriversForm";

import { ConfigNames } from "@/app/store/config/types";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import {
  screen,
  setupMockServer,
  renderWithProviders,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  configurationsResolvers.getConfiguration.handler({
    name: ConfigNames.ENABLE_THIRD_PARTY_DRIVERS,
    value: false,
  })
);
describe("ThirdPartyDriversForm", () => {
  it("sets enable_third_party_drivers value", async () => {
    mockServer.use(
      configurationsResolvers.getConfiguration.handler({
        name: ConfigNames.ENABLE_THIRD_PARTY_DRIVERS,
        value: false,
      })
    );
    renderWithProviders(<ThirdPartyDriversForm />);
    await waitForLoading();
    expect(
      screen.getByRole("checkbox", { name: TPDFormLabels.CheckboxLabel })
    ).toHaveProperty("checked", false);
  });
});
