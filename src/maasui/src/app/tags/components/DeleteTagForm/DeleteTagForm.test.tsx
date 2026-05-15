import * as reduxToolkit from "@reduxjs/toolkit";
import type { Mock } from "vitest";

import DeleteTagForm from "./DeleteTagForm";

import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

const callId = "mocked-nanoid";
vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

let state: RootState;
let scrollToSpy: Mock;

beforeEach(() => {
  vi.spyOn(query, "generateCallId").mockReturnValue(callId);
  vi.spyOn(reduxToolkit, "nanoid").mockReturnValue(callId);
  state = factory.rootState({
    machine: factory.machineState({
      items: [
        factory.machine({
          status: NodeStatus.DEPLOYED,
          tags: [1],
        }),
      ],
    }),
    tag: factory.tagState({
      items: [factory.tag({ id: 1 })],
    }),
  });
  // Mock the scrollTo method as jsdom doesn't support this and will error.
  scrollToSpy = vi.fn();
  global.scrollTo = scrollToSpy;
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("dispatches an action to delete a tag", async () => {
  const { store } = renderWithProviders(<DeleteTagForm id={1} />, { state });
  await userEvent.click(screen.getByRole("button", { name: "Delete" }));
  const expected = tagActions.delete(1);
  await waitFor(() => {
    expect(
      store.getActions().find((action) => action.type === expected.type)
    ).toStrictEqual(expected);
  });
});

it("displays a message when deleting a tag on a machine", async () => {
  state.tag.items = [
    factory.tag({
      id: 1,
      machine_count: 4,
      name: "tag1",
    }),
  ];
  renderWithProviders(<DeleteTagForm id={1} />, { state });
  expect(
    screen.getByText(
      "tag1 will be deleted and unassigned from every tagged machine. Are you sure?"
    )
  ).toBeInTheDocument();
});

it("displays a message when deleting a tag not on a machine", async () => {
  state.tag.items = [
    factory.tag({
      id: 1,
      machine_count: 0,
      name: "tag1",
    }),
  ];
  renderWithProviders(<DeleteTagForm id={1} />, { state });
  expect(
    screen.getByText("tag1 will be deleted. Are you sure?")
  ).toBeInTheDocument();
});
