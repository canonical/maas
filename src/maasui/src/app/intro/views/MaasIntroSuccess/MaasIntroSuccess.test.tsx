import { waitFor } from "@testing-library/react";

import MaasIntroSuccess, {
  Labels as MaasIntroSuccessLabels,
} from "./MaasIntroSuccess";

import urls from "@/app/base/urls";
import { configActions } from "@/app/store/config";
import { ConfigNames } from "@/app/store/config/types";
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

describe("MaasIntroSuccess", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({ name: ConfigNames.COMPLETED_INTRO, value: false }),
        ],
      }),
    });
  });

  it("links to the user intro if not yet completed", () => {
    mockServer.use(
      authResolvers.getCurrentUser.handler(factory.user()),
      authResolvers.getMeStatistics.handler(
        factory.userStatistics({ completed_intro: false })
      )
    );
    renderWithProviders(<MaasIntroSuccess />, {
      initialEntries: ["/intro/success"],
      state,
    });
    expect(
      screen.getByRole("link", { name: MaasIntroSuccessLabels.FinishSetup })
    ).toHaveAttribute("href", urls.intro.user);
  });

  it("links to the machine list if an admin that has completed the user intro", async () => {
    mockServer.use(
      authResolvers.getCurrentUser.handler(
        factory.user({ is_superuser: true })
      ),
      authResolvers.getMeStatistics.handler(
        factory.userStatistics({ completed_intro: true })
      )
    );
    renderWithProviders(<MaasIntroSuccess />, {
      initialEntries: ["/intro/success"],
      state,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: MaasIntroSuccessLabels.FinishSetup })
      ).toHaveAttribute("href", urls.machines.index);
    });
  });

  it("links to the machine list if a non-admin that has completed the user intro", async () => {
    mockServer.use(
      authResolvers.getCurrentUser.handler(
        factory.user({ is_superuser: false })
      ),
      authResolvers.getMeStatistics.handler(
        factory.userStatistics({ completed_intro: true })
      )
    );

    renderWithProviders(<MaasIntroSuccess />, {
      initialEntries: ["/intro/success"],
      state,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: MaasIntroSuccessLabels.FinishSetup })
      ).toHaveAttribute("href", urls.machines.index);
    });
  });

  it("dispatches an action to update completed intro config", async () => {
    const { store } = renderWithProviders(<MaasIntroSuccess />, {
      initialEntries: ["/intro/success"],
      state,
    });

    await userEvent.click(
      screen.getByRole("link", { name: MaasIntroSuccessLabels.FinishSetup })
    );

    const expectedAction = configActions.update({ completed_intro: true });
    const actualActions = store.getActions();
    expect(
      actualActions.find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });
});
