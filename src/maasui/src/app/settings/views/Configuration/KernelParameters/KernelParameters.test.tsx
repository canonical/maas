import { Labels as KPFormLabels } from "../KernelParametersForm/KernelParametersForm";

import KernelParameters, {
  Labels as KernelParametersLabels,
} from "./KernelParameters";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("KernelParameters", () => {
  let initialState: RootState;

  beforeEach(() => {
    initialState = factory.rootState({
      config: factory.configState({
        items: [
          {
            name: ConfigNames.KERNEL_OPTS,
            value: "foo",
          },
        ],
      }),
    });
  });

  it("displays a spinner if config is loading", () => {
    const state = { ...initialState };
    state.config.loading = true;
    renderWithProviders(<KernelParameters />, { state });
    expect(
      screen.getByText(KernelParametersLabels.Loading)
    ).toBeInTheDocument();
  });

  it("displays the KernelParameters form if config is loaded", () => {
    const state = { ...initialState };
    state.config.loaded = true;
    renderWithProviders(<KernelParameters />, { state });
    expect(
      screen.getByRole("form", { name: KPFormLabels.FormLabel })
    ).toBeInTheDocument();
  });

  it("dispatches action to fetch config if not already loaded", () => {
    const state = { ...initialState };
    state.config.loaded = false;
    const { store } = renderWithProviders(<KernelParameters />, { state });
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
