import { Route, Routes } from "react-router";
import type { Mock } from "vitest";

import TagsHeader, { Label } from "./TagDetailsHeader";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

let scrollToSpy: Mock;

beforeEach(() => {
  // Mock the scrollTo method as jsdom doesn't support this and will error.
  scrollToSpy = vi.fn();
  global.scrollTo = scrollToSpy;
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("displays edit and delete buttons, and a return link", () => {
  const tag = factory.tag({ id: 1 });
  const state = factory.rootState({
    tag: factory.tagState({
      loaded: true,
      loading: false,
      items: [tag],
    }),
  });
  renderWithProviders(
    <Routes>
      <Route
        element={<TagsHeader onDelete={vi.fn()} onUpdate={vi.fn()} />}
        path={urls.tags.tag.index(null)}
      />
    </Routes>,
    {
      initialEntries: [urls.tags.tag.index({ id: 1 })],
      state,
    }
  );

  expect(
    screen.getByRole("link", { name: /Back to all tags/i })
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: Label.DeleteButton })
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: Label.EditButton })
  ).toBeInTheDocument();
});

it("triggers onUpdate with the correct tag ID", async () => {
  const onUpdate = vi.fn();
  const tag = factory.tag({ id: 1 });
  const state = factory.rootState({
    tag: factory.tagState({
      loaded: true,
      loading: false,
      items: [tag],
    }),
  });
  renderWithProviders(
    <Routes>
      <Route
        element={<TagsHeader onDelete={vi.fn()} onUpdate={onUpdate} />}
        path={urls.tags.tag.index(null)}
      />
    </Routes>,
    { initialEntries: [urls.tags.tag.index({ id: 1 })], state }
  );
  await userEvent.click(screen.getByRole("button", { name: "Edit" }));
  expect(onUpdate).toBeCalledWith(1);
});
