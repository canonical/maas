import * as reduxToolkit from "@reduxjs/toolkit";

import TagForm, { Label } from "./TagForm";
import { Label as TagFormChangesLabel } from "./TagFormChanges";
import { Label as TagFormFieldsLabel } from "./TagFormFields";

import { Label as AddTagFormLabel } from "@/app/base/components/NodeTagForm/NodeTagForm";
import { machineActions } from "@/app/store/machine";
import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { tagStateListFactory } from "@/testing/factories/state";
import { mockFormikFormSaved } from "@/testing/mockFormikFormSaved";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

let state: RootState;
beforeEach(() => {
  vi.spyOn(query, "generateCallId").mockReturnValue("mocked-nanoid");
  vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("mocked-nanoid");
  const tags = [
    factory.tag({ id: 1, name: "tag1" }),
    factory.tag({ id: 2, name: "tag2" }),
  ];
  state = factory.rootState({
    tag: factory.tagState({
      items: tags,
      loaded: true,
      lists: {
        "mocked-nanoid": tagStateListFactory({
          items: [
            factory.tag({ id: 1, name: "tag1" }),
            factory.tag({ id: 2, name: "tag2" }),
          ],
          loaded: true,
        }),
      },
    }),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("dispatches action to fetch tags on load", async () => {
  const machines = [
    factory.machine({ system_id: "abc123", tags: [] }),
    factory.machine({ system_id: "def456", tags: [] }),
  ];
  state.machine.items = machines;
  state.machine.selected = {
    items: machines.map((machine) => machine.system_id),
  };
  const { store } = renderWithProviders(<TagForm isViewingDetails={false} />, {
    state,
  });

  expect(store.getActions().some((action) => action.type === "tag/fetch")).toBe(
    true
  );
});

it("correctly dispatches actions to tag machines", async () => {
  const machines = [
    factory.machine({ system_id: "abc123", tags: [] }),
    factory.machine({ system_id: "def456", tags: [] }),
  ];
  state.machine.items = machines;
  state.machine.selected = {
    items: machines.map((machine) => machine.system_id),
  };
  const { store } = renderWithProviders(<TagForm isViewingDetails={false} />, {
    state,
  });

  await userEvent.click(
    screen.getByRole("textbox", { name: TagFormFieldsLabel.TagInput })
  );
  await userEvent.click(screen.getByRole("option", { name: "tag1" }));
  await userEvent.click(screen.getByRole("option", { name: "tag2" }));
  await userEvent.click(
    screen.getByRole("button", { name: /Save tag changes/i })
  );

  await waitFor(() => {
    const expectedActions = [
      machineActions.tag(
        { filter: { id: ["abc123", "def456"] }, tags: [1, 2] },
        "mocked-nanoid"
      ),
    ];
    const actualActions = store
      .getActions()
      .filter((action) => action.type === expectedActions[0].type);
    expect(actualActions).toStrictEqual(expectedActions);
  });
});

it("correctly dispatches actions to untag machines", async () => {
  const machines = [
    factory.machine({ system_id: "abc123", tags: [1, 2] }),
    factory.machine({ system_id: "def456", tags: [1, 2] }),
  ];
  state.tag.lists = {
    "mocked-nanoid": tagStateListFactory({
      items: [
        factory.tag({ id: 1, name: "tag1", machine_count: 1 }),
        factory.tag({ id: 2, name: "tag2", machine_count: 1 }),
      ],
      loaded: true,
    }),
  };
  state.machine.items = machines;
  state.machine.selected = {
    items: machines.map((machine) => machine.system_id),
  };
  const { store } = renderWithProviders(<TagForm isViewingDetails={false} />, {
    state,
  });

  const deleteButtons = screen.getAllByRole("button", {
    name: TagFormChangesLabel.Remove,
  });
  await userEvent.click(deleteButtons[0]);
  await userEvent.click(deleteButtons[1]);
  await userEvent.click(
    screen.getByRole("button", { name: /Save tag changes/i })
  );

  await waitFor(() => {
    const expectedActions = [
      machineActions.untag(
        {
          filter: { id: ["abc123", "def456"] },
          tags: [1, 2],
        },
        "mocked-nanoid"
      ),
    ];
    const actualActions = store
      .getActions()
      .filter((action) => action.type === expectedActions[0].type);
    expect(actualActions).toStrictEqual(expectedActions);
  });
});

it("correctly dispatches actions to tag and untag a machine", async () => {
  const machines = [factory.machine({ system_id: "abc123", tags: [1] })];
  state.machine.items = machines;
  state.machine.selected = {
    items: machines.map((machine) => machine.system_id),
  };
  const { store } = renderWithProviders(<TagForm isViewingDetails={false} />, {
    state,
  });

  await userEvent.click(
    screen.getByRole("textbox", { name: TagFormFieldsLabel.TagInput })
  );
  await userEvent.click(screen.getByRole("option", { name: "tag2" }));
  await userEvent.click(
    screen.getByRole("button", { name: TagFormChangesLabel.Remove })
  );
  await userEvent.click(
    screen.getByRole("button", { name: /Save tag changes/i })
  );

  await waitFor(() => {
    const expectedActions = [
      machineActions.tag(
        { filter: { id: ["abc123"] }, tags: [2] },
        "mocked-nanoid"
      ),
      machineActions.untag(
        { filter: { id: ["abc123"] }, tags: [1] },
        "mocked-nanoid"
      ),
    ];
    const actualActions = store
      .getActions()
      .filter(
        (action) =>
          action.type === expectedActions[0].type ||
          action.type === expectedActions[1].type
      );
    expect(actualActions).toStrictEqual(expectedActions);
  });
});

it("shows saving label if not viewing from machine config page", () => {
  const machines = [
    factory.machine({ system_id: "abc123", tags: [] }),
    factory.machine({ system_id: "def456", tags: [] }),
  ];
  state.machine.actions["mocked-nanoid"] = factory.machineActionState({
    status: "loading",
  });
  state.machine.items = machines;
  state.machine.selected = {
    items: machines.map((machine) => machine.system_id),
  };
  renderWithProviders(
    <TagForm isViewingDetails={false} isViewingMachineConfig={false} />,
    {
      state,
    }
  );

  expect(screen.getByTestId("saving-label")).toBeInTheDocument();
  vi.restoreAllMocks();
});

it("does not show saving label if viewing from machine config page", () => {
  const machines = [
    factory.machine({ system_id: "abc123", tags: [] }),
    factory.machine({ system_id: "def456", tags: [] }),
  ];
  state.machine.items = machines;
  state.machine.selected = {
    items: machines.map((machine) => machine.system_id),
  };
  renderWithProviders(
    <TagForm isViewingDetails={false} isViewingMachineConfig />,
    {
      state,
    }
  );

  expect(screen.queryByTestId("saving-label")).not.toBeInTheDocument();
});

it("shows a notification on success", async () => {
  const machines = [factory.machine({ system_id: "abc123", tags: [1] })];
  state.machine.items = machines;
  state.machine.selected = {
    items: machines.map((machine) => machine.system_id),
  };
  const { store } = renderWithProviders(<TagForm isViewingDetails={false} />, {
    state,
  });
  // Mock state.tag.saved transitioning from "false" to "true"
  mockFormikFormSaved();
  await userEvent.click(
    screen.getByRole("textbox", { name: TagFormFieldsLabel.TagInput })
  );
  await userEvent.click(screen.getByRole("option", { name: "tag2" }));
  await userEvent.click(
    screen.getByRole("button", { name: TagFormChangesLabel.Remove })
  );
  await userEvent.click(
    screen.getByRole("button", { name: /Save tag changes/i })
  );

  await waitFor(() => {
    const action = store
      .getActions()
      .find((action) => action.type === "message/add");
    expect(action.payload.message).toBe(Label.Saved);
  });
});

it("can open a create tag form", async () => {
  const machines = [factory.machine({ system_id: "abc123", tags: [1] })];
  state.machine.items = machines;
  state.machine.selected = {
    items: machines.map((machine) => machine.system_id),
  };
  renderWithProviders(<TagForm isViewingDetails={false} />, {
    state,
  });

  await userEvent.type(
    screen.getByRole("textbox", { name: TagFormFieldsLabel.TagInput }),
    "name1{enter}"
  );
  await waitFor(() => {
    expect(
      screen.getByRole("form", { name: AddTagFormLabel.Form })
    ).toBeInTheDocument();
  });
});

it("updates the new tags after creating a tag", async () => {
  const machines = [factory.machine({ system_id: "abc123", tags: [1] })];
  state.machine.items = machines;
  state.machine.selected = {
    items: machines.map((machine) => machine.system_id),
  };
  renderWithProviders(<TagForm isViewingDetails={false} />, {
    state,
  });
  expect(
    screen.queryByRole("button", { name: /new-tag/i })
  ).not.toBeInTheDocument();
  await userEvent.type(
    screen.getByRole("textbox", { name: TagFormFieldsLabel.TagInput }),
    "new-tag{enter}"
  );
  mockFormikFormSaved();
  const newTag = factory.tag({ id: 8, name: "new-tag" });
  state.tag.saved = true;
  state.tag.items.push(newTag);
  await userEvent.click(
    screen.getByRole("button", { name: AddTagFormLabel.Submit })
  );
  const changes = screen.getByRole("table", {
    name: TagFormChangesLabel.Table,
  });
  await waitFor(() => {
    expect(
      within(changes).getByRole("button", { name: /new-tag/i })
    ).toBeInTheDocument();
  });
});
