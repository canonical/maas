import { Labels as WindowsFormLabels } from "../WindowsForm/WindowsForm";

import Windows, { Labels as WindowsLabels } from "./Windows";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("Windows", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        loading: false,
        loaded: true,
        items: [
          factory.config({
            name: ConfigNames.WINDOWS_KMS_HOST,
            value: "127.0.0.1",
          }),
        ],
      }),
    });
  });

  it("displays a spinner if config is loading", () => {
    state.config.loading = true;
    renderWithProviders(<Windows />, { state });
    expect(screen.getByText(WindowsLabels.Loading)).toBeInTheDocument();
  });

  it("displays the Windows form if config is loaded", () => {
    state.config.loaded = true;
    renderWithProviders(<Windows />, { state });
    expect(
      screen.getByRole("form", { name: WindowsFormLabels.FormLabel })
    ).toBeInTheDocument();
  });

  it("dispatches action to fetch config if not already loaded", () => {
    state.config.loaded = false;
    const { store } = renderWithProviders(<Windows />, { state });
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
