import * as reduxToolkit from "@reduxjs/toolkit";

import CloneForm from "./CloneForm";

import { machineActions } from "@/app/store/machine";
import * as query from "@/app/store/machine/utils/query";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

describe("CloneForm", () => {
  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValue("123456");
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("123456");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should be submittable only when a machine and cloning config are selected", async () => {
    const machines = [
      factory.machine({ system_id: "abc123" }),
      factory.machineDetails({
        disks: [factory.nodeDisk()],
        interfaces: [factory.machineInterface()],
        system_id: "def456",
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        active: null,
        items: machines,
        loaded: true,
        selected: { items: ["abc123"] },
        lists: {
          "123456": factory.machineStateList({
            groups: [
              factory.machineStateListGroup({
                items: [machines[1].system_id],
              }),
            ],
            loaded: true,
          }),
        },
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
          def456: factory.machineStatus(),
        }),
      }),
    });
    state.fabric.loaded = true;
    state.subnet.loaded = true;
    state.vlan.loaded = true;
    renderWithProviders(<CloneForm isViewingDetails={false} />, {
      state,
    });

    // Checkboxes and submit should be disabled at first.
    expect(
      screen.getByRole("button", { name: "Clone to machine" })
    ).toBeDisabled();
    expect(
      screen.getByRole("checkbox", { name: "Clone network configuration" })
    ).toBeDisabled();

    // Select a source machine - form should update
    await userEvent.click(
      screen.getByRole("row", { name: machines[1].hostname })
    );

    expect(
      screen.getByRole("button", { name: "Clone to machine" })
    ).toBeDisabled();

    await waitFor(() => {
      expect(
        screen.getByRole("checkbox", { name: "Clone network configuration" })
      ).toBeEnabled();
    });

    // Select config to clone - submit should be re-disabled.
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Clone network configuration" })
    );

    expect(
      screen.getByRole("checkbox", { name: "Clone network configuration" })
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Clone to machine" })
    ).toBeEnabled();
  });

  // TODO: v2 state updates cannot be done without rerendering the component
  //  and losing internal state, re-add this test when v3 is available
  it.todo("shows cloning results when the form is successfully submitted");

  it("can dispatch an action to clone to the given machines", async () => {
    const machines = [
      factory.machine({ system_id: "abc123" }),
      factory.machine({ system_id: "def456" }),
      factory.machineDetails({
        disks: [factory.nodeDisk()],
        interfaces: [factory.machineInterface()],
        system_id: "ghi789",
        hostname: "another-machine",
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        active: null,
        items: machines,
        loaded: true,
        selected: { items: ["abc123", "def456"] },
        lists: {
          "123456": factory.machineStateList({
            groups: [
              factory.machineStateListGroup({
                items: [machines[2].system_id],
              }),
            ],
            loaded: true,
          }),
        },
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
          def456: factory.machineStatus(),
          ghi789: factory.machineStatus(),
        }),
      }),
    });
    state.fabric.loaded = true;
    state.subnet.loaded = true;
    state.vlan.loaded = true;

    const { store } = renderWithProviders(
      <CloneForm isViewingDetails={false} />,
      {
        state,
      }
    );

    await userEvent.click(
      screen.getByRole("row", { name: machines[2].hostname })
    );

    await userEvent.click(
      screen.getByRole("checkbox", { name: "Clone network configuration" })
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Clone to 2 machines" })
    );

    const expectedAction = machineActions.clone(
      {
        filter: { id: ["abc123", "def456"] },
        interfaces: true,
        storage: false,
        system_id: "ghi789",
      },
      "123456"
    );
    const actualAction = store
      .getActions()
      .find((action) => action.type === expectedAction.type);
    expect(actualAction).toStrictEqual(expectedAction);
  });
});
