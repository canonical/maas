import Deploy from "./Deploy";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

let state: RootState;

beforeEach(() => {
  state = factory.rootState();
});

it(`dispatches actions to fetch config and general os info if either has not
    already loaded`, () => {
  state.config.loaded = false;

  const { store } = renderWithProviders(<Deploy />, { state });

  const fetchActions = store
    .getActions()
    .filter(
      (action) =>
        action.type.startsWith("config/fetch") ||
        action.type.startsWith("general/fetch")
    );

  expect(fetchActions).toEqual([
    {
      type: "config/fetch",
      meta: { model: "config", method: "list" },
      payload: null,
    },
    {
      type: "general/fetchOsInfo",
      meta: {
        cache: true,
        model: "general",
        method: "osinfo",
      },
      payload: null,
    },
  ]);
});
