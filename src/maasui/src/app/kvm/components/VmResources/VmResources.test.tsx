import * as reduxToolkit from "@reduxjs/toolkit";

import VmResources, { Label } from "./VmResources";

import { Label as MachineListLabel } from "@/app/machines/views/MachineList/MachineListTable/MachineListTable";
import { machineActions } from "@/app/store/machine";
import * as query from "@/app/store/machine/utils/query";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});
const callId = "mocked-nanoid";

describe("VmResources", () => {
  let state: RootState;

  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValue(callId);
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue(callId);
    const machines = [factory.machine(), factory.machine()];
    state = factory.rootState({
      machine: factory.machineState({
        items: machines,
        lists: {
          [callId]: factory.machineStateList({
            count: machines.length,
            loaded: true,
            groups: [
              factory.machineStateListGroup({
                items: machines.map(({ system_id }) => system_id),
                name: "Deployed",
              }),
            ],
          }),
        },
      }),
      pod: factory.podState({
        items: [factory.pod({ id: 1, name: "pod1", type: PodType.LXD })],
      }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("disables the dropdown if no VMs are provided", () => {
    state.machine.lists[callId].count = 0;
    state.machine.lists[callId].groups = [
      factory.machineStateListGroup({
        items: [],
        name: "Deployed",
      }),
    ];
    renderWithProviders(<VmResources podId={1} />, { state });
    expect(
      screen.getByRole("button", { name: Label.ResourceVMs })
    ).toBeAriaDisabled();
  });

  it("can pass additional filters to the request", () => {
    const { store } = renderWithProviders(
      <VmResources filters={{ id: ["abc123"] }} podId={1} />,
      { state }
    );
    const expected = machineActions.fetch(callId);
    const result = store
      .getActions()
      .find((action) => action.type === expected.type);
    expect(result.payload.params.filter).toStrictEqual({
      id: ["abc123"],
      pod: ["pod1"],
    });
  });

  it("can display a list of VMs", async () => {
    renderWithProviders(<VmResources podId={1} />, {
      state,
    });
    await userEvent.click(
      screen.getByRole("button", { name: Label.ResourceVMs })
    );
    expect(
      screen.getByRole("grid", {
        name: new RegExp(MachineListLabel.Machines, "i"),
      })
    ).toBeInTheDocument();
  });
});
