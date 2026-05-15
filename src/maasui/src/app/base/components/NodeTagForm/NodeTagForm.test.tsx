import NodeTagForm, { Label } from "./NodeTagForm";

import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import { Label as KernelOptionsLabel } from "@/app/tags/components/KernelOptionsField";
import * as factory from "@/testing/factories";
import { mockFormikFormSaved } from "@/testing/mockFormikFormSaved";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

let state: RootState;

beforeEach(() => {
  state = factory.rootState({
    tag: factory.tagState(),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("dispatches an action to create a tag", async () => {
  const { store } = renderWithProviders(
    <NodeTagForm name="new-tag" onTagCreated={vi.fn()} />,
    {
      state,
    }
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: Label.Comment }),
    "comment1"
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: KernelOptionsLabel.KernelOptions }),
    "options1"
  );
  await userEvent.click(screen.getByRole("button", { name: Label.Submit }));
  const expected = tagActions.create({
    comment: "comment1",
    kernel_opts: "options1",
    name: "new-tag",
  });
  await waitFor(() => {
    expect(
      store.getActions().find((action) => action.type === expected.type)
    ).toStrictEqual(expected);
  });
});

it("returns the newly created tag on save", async () => {
  const onTagCreated = vi.fn();
  const newTag = factory.tag({ id: 8, name: "new-tag" });
  state.tag = factory.tagState({
    items: [newTag],
    saved: true,
  });

  renderWithProviders(
    <NodeTagForm name="new-tag" onTagCreated={onTagCreated} />,
    { state, initialEntries: ["/tags"] }
  );

  mockFormikFormSaved();
  await userEvent.click(screen.getByRole("button", { name: Label.Submit }));
  await waitFor(() => {
    expect(onTagCreated).toHaveBeenCalledWith(newTag);
  });
});
