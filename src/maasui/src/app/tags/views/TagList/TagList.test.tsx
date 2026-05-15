import TagList from "./TagList";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

let state: RootState;

beforeEach(() => {
  state = factory.rootState({
    tag: factory.tagState({
      items: [
        factory.tag({
          name: "rad",
        }),
        factory.tag({
          name: "cool",
        }),
      ],
    }),
  });
});

it("renders", () => {
  renderWithProviders(<TagList />, { state, initialEntries: ["/tags"] });
  expect(screen.getByLabelText("pagination")).toBeInTheDocument();
  expect(screen.getByRole("grid")).toBeInTheDocument();
});
