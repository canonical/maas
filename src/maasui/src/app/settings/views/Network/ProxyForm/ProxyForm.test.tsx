import ProxyForm from "./ProxyForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("ProxyForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        loaded: true,
        items: [
          {
            name: ConfigNames.HTTP_PROXY,
            value: "http://www.url.com",
          },
          {
            name: ConfigNames.ENABLE_HTTP_PROXY,
            value: false,
          },
          {
            name: ConfigNames.USE_PEER_PROXY,
            value: false,
          },
        ],
      }),
    });
  });

  it("displays a spinner if config is loading", () => {
    state.config.loading = true;
    renderWithProviders(<ProxyForm />, { state });
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("displays a text input if http proxy is enabled", () => {
    state.config.items = [
      {
        name: ConfigNames.HTTP_PROXY,
        value: "http://www.url.com",
      },
      {
        name: ConfigNames.ENABLE_HTTP_PROXY,
        value: true,
      },
      {
        name: ConfigNames.USE_PEER_PROXY,
        value: false,
      },
    ];
    renderWithProviders(<ProxyForm />, { state });
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("dispatches action to fetch config if not already loaded", () => {
    state.config.loaded = false;
    const { store } = renderWithProviders(<ProxyForm />, { state });
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
