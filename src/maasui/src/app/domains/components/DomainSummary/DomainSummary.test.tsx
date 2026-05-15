import { waitFor } from "@testing-library/react";

import DomainSummary, { Labels as DomainSummaryLabels } from "./DomainSummary";

import { Labels as EditableSectionLabels } from "@/app/base/components/EditableSection";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

const mockServer = setupMockServer(
  authResolvers.getCurrentUser.handler(),
  authResolvers.getMeStatistics.handler()
);

describe("DomainSummary", () => {
  it("render nothing if domain doesn't exist", () => {
    const state = factory.rootState();
    renderWithProviders(<DomainSummary id={1} />, {
      state,
    });

    expect(
      screen.queryByRole("heading", { name: DomainSummaryLabels.Title })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText(DomainSummaryLabels.Summary)
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("form", { name: DomainSummaryLabels.FormLabel })
    ).not.toBeInTheDocument();
  });

  it("renders domain summary", () => {
    const state = factory.rootState({
      domain: factory.domainState({
        items: [factory.domain({ id: 1, name: "test" })],
      }),
    });

    renderWithProviders(<DomainSummary id={1} />, {
      state,
    });

    expect(
      screen.getByRole("heading", { name: DomainSummaryLabels.Title })
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(DomainSummaryLabels.Summary)
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("form", { name: DomainSummaryLabels.FormLabel })
    ).not.toBeInTheDocument();
  });

  it("doesn't render Edit button when user is not admin", async () => {
    const state = factory.rootState({
      domain: factory.domainState({
        items: [factory.domain({ id: 1, name: "test" })],
      }),
    });
    mockServer.use(
      authResolvers.getCurrentUser.handler(
        factory.user({ is_superuser: false })
      )
    );

    renderWithProviders(<DomainSummary id={1} />, {
      state,
    });

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: EditableSectionLabels.EditButton })
      ).not.toBeInTheDocument();
    });
  });

  describe("when user is admin", () => {
    let state: RootState;

    beforeEach(() => {
      state = factory.rootState({
        domain: factory.domainState({
          items: [
            factory.domain({
              id: 1,
              name: "test",
            }),
          ],
        }),
      });
    });

    it("renders the Edit button", () => {
      renderWithProviders(<DomainSummary id={1} />, {
        state,
      });

      expect(
        screen.getAllByRole("button", {
          name: EditableSectionLabels.EditButton,
        })[0]
      ).toBeInTheDocument();
    });

    it("renders the form when Edit button is clicked", async () => {
      renderWithProviders(<DomainSummary id={1} />, {
        state,
      });

      await userEvent.click(
        screen.getAllByRole("button", {
          name: EditableSectionLabels.EditButton,
        })[0]
      );

      expect(
        screen.queryByLabelText(DomainSummaryLabels.Summary)
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("form", { name: DomainSummaryLabels.FormLabel })
      ).toBeInTheDocument();
    });

    it("closes the form when Cancel button is clicked", async () => {
      renderWithProviders(<DomainSummary id={1} />, {
        state,
      });

      await userEvent.click(
        screen.getAllByRole("button", {
          name: EditableSectionLabels.EditButton,
        })[0]
      );

      await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

      expect(
        screen.getByLabelText(DomainSummaryLabels.Summary)
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("form", { name: DomainSummaryLabels.FormLabel })
      ).not.toBeInTheDocument();
    });

    it("calls actions.update on save click", async () => {
      const { store } = renderWithProviders(<DomainSummary id={1} />, {
        state,
      });

      await userEvent.click(
        screen.getAllByRole("button", {
          name: EditableSectionLabels.EditButton,
        })[0]
      );

      await userEvent.clear(
        screen.getByRole("textbox", { name: DomainSummaryLabels.Name })
      );

      await userEvent.type(
        screen.getByRole("textbox", { name: DomainSummaryLabels.Name }),
        "test"
      );

      await userEvent.type(
        screen.getByRole("spinbutton", { name: DomainSummaryLabels.Ttl }),
        "42"
      );

      await userEvent.click(
        screen.getByRole("button", { name: DomainSummaryLabels.SubmitLabel })
      );

      expect(
        store.getActions().find((action) => action.type === "domain/update")
      ).toStrictEqual({
        type: "domain/update",
        meta: {
          method: "update",
          model: "domain",
        },
        payload: {
          params: {
            id: 1,
            name: "test",
            ttl: 42,
            authoritative: false,
          },
        },
      });
    });
  });
});
