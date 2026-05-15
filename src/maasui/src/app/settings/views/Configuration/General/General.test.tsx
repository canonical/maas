import { Labels as FormLabels } from "../GeneralForm/GeneralForm";

import General, { Labels as GeneralLabels } from "./General";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("General", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [
          {
            name: ConfigNames.MAAS_NAME,
            value: "bionic",
          },
          {
            name: ConfigNames.ENABLE_ANALYTICS,
            value: true,
          },
          {
            name: ConfigNames.RELEASE_NOTIFICATIONS,
            value: true,
          },
        ],
      }),
    });
  });

  it("displays a spinner if config is loading", () => {
    state.config.loading = true;
    renderWithProviders(<General />, { state });
    expect(screen.getByText(GeneralLabels.Loading)).toBeInTheDocument();
  });

  it("displays the General form if config is loaded", () => {
    state.config.loaded = true;
    renderWithProviders(<General />, { state });
    expect(
      screen.getByRole("form", { name: FormLabels.FormLabel })
    ).toBeInTheDocument();
  });

  it("dispatches action to fetch config if not already loaded", () => {
    state.config.loaded = false;
    const { store } = renderWithProviders(<General />, { state });

    const fetchActions = store
      .getActions()
      .filter((action) => action.type.endsWith("fetch"));

    expect(fetchActions).toEqual([
      {
        type: "config/fetch",
        meta: {
          model: "config",
          method: "list",
        },
        payload: null,
      },
    ]);
  });
});
