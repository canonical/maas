import { waitFor } from "@testing-library/react";
import type { MockInstance } from "vitest";

import UserIntro, { Labels as UserIntroLabels } from "./UserIntro";

import * as baseHooks from "@/app/base/hooks/base";
import urls from "@/app/base/urls";
import { authResolvers } from "@/testing/resolvers/auth";
import { sshKeyResolvers } from "@/testing/resolvers/sshKeys";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitForLoading,
  within,
} from "@/testing/utils";

const mockServer = setupMockServer(
  sshKeyResolvers.listSshKeys.handler(),
  authResolvers.getCurrentUser.handler(),
  authResolvers.getMeStatistics.handler(),
  authResolvers.completeIntro.handler()
);

describe("UserIntro", () => {
  let markedIntroCompleteMock: MockInstance;
  beforeEach(() => {
    markedIntroCompleteMock = vi
      .spyOn(baseHooks, "useCycled")
      .mockImplementation(
        () => [false, () => null] as ReturnType<typeof baseHooks.useCycled>
      );
  });

  it("displays a green tick icon when there are ssh keys", async () => {
    renderWithProviders(<UserIntro />, {
      initialEntries: ["/intro/user"],
    });

    await waitForLoading();

    const icon = screen.getByLabelText("success");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass("p-icon--success");
  });

  it("displays a grey tick icon when there are no ssh keys", async () => {
    mockServer.use(
      sshKeyResolvers.listSshKeys.handler({ items: [], total: 0 })
    );
    renderWithProviders(<UserIntro />, {
      initialEntries: ["/intro/user"],
    });

    await waitForLoading();
    const icon = screen.getByLabelText("success-grey");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass("p-icon--success-grey");
  });

  it("redirects if the user has already completed the intro", async () => {
    const { router } = renderWithProviders(<UserIntro />, {
      initialEntries: ["/intro/user"],
    });
    await waitForLoading();
    expect(router.state.location.pathname).toBe(urls.machines.index);
  });

  it("disables the continue button if there are no ssh keys", async () => {
    mockServer.use(
      sshKeyResolvers.listSshKeys.handler({ items: [], total: 0 })
    );
    renderWithProviders(<UserIntro />, {
      initialEntries: ["/intro/user"],
    });

    await waitForLoading();

    expect(
      screen.getByRole("button", { name: UserIntroLabels.Continue })
    ).toBeDisabled();
  });

  it("hides the SSH list if there are no ssh keys", async () => {
    mockServer.use(
      sshKeyResolvers.listSshKeys.handler({ items: [], total: 0 })
    );
    renderWithProviders(<UserIntro />, {
      initialEntries: ["/intro/user"],
    });

    await waitForLoading();
    expect(
      screen.queryByRole("grid", { name: "SSH keys" })
    ).not.toBeInTheDocument();
  });

  it("shows the SSH list if there are ssh keys", async () => {
    renderWithProviders(<UserIntro />, {
      initialEntries: ["/intro/user"],
    });

    await waitForLoading();

    expect(screen.getByTestId("ssh-keys-table")).toBeInTheDocument();
  });

  it("marks the intro as completed when clicking the continue button", async () => {
    renderWithProviders(<UserIntro />, {
      initialEntries: ["/intro/user"],
    });

    await waitForLoading();
    await userEvent.click(
      screen.getByRole("button", { name: UserIntroLabels.Continue })
    );

    await waitFor(() => {
      expect(authResolvers.completeIntro.resolved).toBe(true);
    });
  });

  it("can show errors when trying to update the user", async () => {
    mockServer.use(
      authResolvers.getCurrentUser.error({ code: 400, message: "Uh oh" })
    );
    renderWithProviders(<UserIntro />, {
      initialEntries: ["/intro/user"],
    });
    await waitForLoading();
    expect(screen.getByText("Error:")).toBeInTheDocument();
    expect(screen.getByText("Uh oh")).toBeInTheDocument();
  });

  it("redirects when the user has been updated", async () => {
    // Mock the markedIntroComplete state to simulate the markingIntroComplete
    // state having gone from true to false.
    markedIntroCompleteMock.mockImplementationOnce(() => [true, () => null]);
    const { router } = renderWithProviders(<UserIntro />, {
      initialEntries: ["/intro/user"],
    });
    await waitForLoading();
    expect(router.state.location.pathname).toBe(urls.machines.index);
  });

  it("can skip the user setup", async () => {
    renderWithProviders(<UserIntro />, {
      initialEntries: ["/intro/user"],
    });
    await waitForLoading();

    // Open the skip confirmation.
    await userEvent.click(
      screen.getByRole("button", { name: UserIntroLabels.Skip })
    );

    // Confirm skipping MAAS setup.
    const confirm = screen.getByTestId("skip-setup");
    expect(confirm).toBeInTheDocument();

    await userEvent.click(
      within(confirm).getByRole("button", { name: UserIntroLabels.Skip })
    );

    await waitFor(() => {
      expect(authResolvers.completeIntro.resolved).toBe(true);
    });
  });
});
