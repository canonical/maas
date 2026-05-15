import NtpForm from "./NtpForm";

import { ConfigNames } from "@/app/store/config/types";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import {
  userEvent,
  screen,
  setupMockServer,
  renderWithProviders,
  mockIsPending,
  waitFor,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  configurationsResolvers.listConfigurations.handler({
    items: [
      { name: ConfigNames.NTP_EXTERNAL_ONLY, value: false },
      { name: ConfigNames.NTP_SERVERS, value: "" },
    ],
  }),
  configurationsResolvers.setBulkConfigurations.handler()
);

describe("NtpForm", () => {
  it("displays a spinner if config is loading", () => {
    mockIsPending();

    renderWithProviders(<NtpForm />);

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("shows errors encountered when fetching configurations", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.error({
        message: "Uh oh!",
        code: 500,
      })
    );

    renderWithProviders(<NtpForm />);

    await waitFor(() => {
      expect(screen.getByText("Uh oh!")).toBeInTheDocument();
    });
  });

  it("updates config on save button click", async () => {
    renderWithProviders(<NtpForm />);

    await waitForLoading();

    await userEvent.type(
      screen.getByRole("textbox", { name: "Addresses of NTP servers" }),
      "ntp.test"
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(configurationsResolvers.setBulkConfigurations.resolved).toBe(true);
  });
});
