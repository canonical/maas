import SyslogForm from "./SyslogForm";

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
  userEvent,
  waitFor,
} from "@/testing/utils";

const mockServer = setupMockServer(
  configurationsResolvers.getConfiguration.handler({
    name: ConfigNames.REMOTE_SYSLOG,
    value: "",
  }),
  configurationsResolvers.setConfiguration.handler()
);
describe("SyslogForm", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        loaded: true,
      }),
    });
  });

  it("renders the syslog form", async () => {
    renderWithProviders(<SyslogForm />, { state });
    await waitForLoading();
    expect(
      screen.getByRole("textbox", {
        name: "Remote syslog server to forward machine logs",
      })
    ).toHaveValue("");
  });
  it("updates the syslog form", async () => {
    renderWithProviders(<SyslogForm />, { state });
    await waitForLoading();
    await userEvent.type(
      screen.getByRole("textbox", {
        name: "Remote syslog server to forward machine logs",
      }),
      "0.0.0.0"
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(configurationsResolvers.setConfiguration.resolved).toBe(true);
    });
  });

  it("displays a spinner if config is loading", () => {
    mockIsPending();
    renderWithProviders(<SyslogForm />, { state });

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("shows an error message when fetching configurations fails", async () => {
    mockServer.use(
      configurationsResolvers.getConfiguration.error({
        code: 500,
        message: "Failed to fetch configurations",
      })
    );

    renderWithProviders(<SyslogForm />, { state });

    await waitFor(() => {
      expect(
        screen.getByText("Error while fetching network configurations")
      ).toBeInTheDocument();
    });
  });
  it("shows an error message when saving configurations fails", async () => {
    mockServer.use(
      configurationsResolvers.setConfiguration.error({
        code: 500,
        message: "Failed to save configurations",
      })
    );

    renderWithProviders(<SyslogForm />, { state });
    await waitForLoading();
    await userEvent.type(
      screen.getByRole("textbox", {
        name: "Remote syslog server to forward machine logs",
      }),
      "0.0.0.0"
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to save configurations")
      ).toBeInTheDocument();
    });
  });
});
