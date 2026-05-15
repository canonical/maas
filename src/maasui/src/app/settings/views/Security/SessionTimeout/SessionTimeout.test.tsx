import { screen } from "@testing-library/react";

import SessionTimeout, {
  Labels as SessionTimeoutLabels,
} from "./SessionTimeout";

import * as configurationsQueryHooks from "@/app/api/query/configurations";
import type { RootState } from "@/app/store/root/types";
import { mockFormikFormSaved } from "@/testing/mockFormikFormSaved";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import {
  userEvent,
  renderWithProviders,
  getTestState,
  setupMockServer,
  mockIsPending,
  waitForLoading,
  waitFor,
  spyOnMutation,
} from "@/testing/utils";

const mockServer = setupMockServer(
  configurationsResolvers.listConfigurations.handler(),
  configurationsResolvers.setBulkConfigurations.handler()
);

describe("SessionTimeout", () => {
  let state: RootState;
  const configItems = getTestState().config.items;
  beforeEach(() => {
    state = getTestState();
  });

  it("displays a spinner while loading", () => {
    mockIsPending();
    renderWithProviders(<SessionTimeout />, { state });

    expect(screen.getByText(SessionTimeoutLabels.Loading)).toBeInTheDocument();
  });

  it("displays the form with correct values", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );
    renderWithProviders(<SessionTimeout />, { state });
    await waitForLoading();
    expect(
      screen.getByRole("form", {
        name: SessionTimeoutLabels.ConfigureTokenExpiration,
      })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration })
    ).toHaveValue("14 days");
  });

  it("displays the updated timeout length when the value is saved", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );
    renderWithProviders(<SessionTimeout />, { state });
    await waitForLoading();
    await userEvent.clear(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration })
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration }),
      "3 hours"
    );

    await userEvent.click(
      screen.getByRole("button", { name: SessionTimeoutLabels.Save })
    );

    mockFormikFormSaved();
    await waitFor(() => {
      expect(configurationsResolvers.setBulkConfigurations.resolved).toBe(true);
    });
    expect(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration })
    ).toHaveValue("3 hours");
  });

  it("disables the submit button if an invalid value is entered", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );
    renderWithProviders(<SessionTimeout />, { state });
    await waitForLoading();
    await userEvent.clear(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration })
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration }),
      "randomtext"
    );

    expect(
      screen.getByRole("button", { name: SessionTimeoutLabels.Save })
    ).toBeDisabled();

    await userEvent.clear(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration })
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration }),
      "2hrs 3mins"
    );

    expect(
      screen.getByRole("button", { name: SessionTimeoutLabels.Save })
    ).toBeDisabled();

    await userEvent.clear(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration })
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration }),
      "20 weeks and 12 nanoseconds"
    );

    expect(
      screen.getByRole("button", { name: SessionTimeoutLabels.Save })
    ).toBeDisabled();

    await userEvent.clear(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration })
    );
    // Minimum boundary
    await userEvent.type(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration }),
      "5 minutes"
    );

    expect(
      screen.getByRole("button", { name: SessionTimeoutLabels.Save })
    ).toBeDisabled();

    await userEvent.clear(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration })
    );
    // Maximum boundary
    await userEvent.type(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration }),
      "90 days"
    );

    expect(
      screen.getByRole("button", { name: SessionTimeoutLabels.Save })
    ).toBeDisabled();
  });

  it("correctly converts time values to seconds on save", async () => {
    mockServer.use(
      configurationsResolvers.listConfigurations.handler({ items: configItems })
    );

    const mockMutate = spyOnMutation(
      configurationsQueryHooks,
      "useBulkSetConfigurations"
    );
    renderWithProviders(<SessionTimeout />, { state });
    await waitForLoading();
    await userEvent.clear(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: SessionTimeoutLabels.Expiration }),
      "1 week 5 days 2 hours"
    );

    await userEvent.click(
      screen.getByRole("button", { name: SessionTimeoutLabels.Save })
    );

    await waitFor(() => {
      expect(configurationsResolvers.setBulkConfigurations.resolved).toBe(true);
    });

    await waitFor(() => {
      expect(mockMutate.mock.calls[0][0]).toMatchObject({
        body: {
          configurations: [
            {
              name: "refresh_token_duration",
              value: 1044000,
            },
          ],
        },
      });
    });
  });
});
