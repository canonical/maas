import { Labels as SourceMachineDetailsLabel } from "./SourceMachineDetails/SourceMachineDetails";
import SourceMachineSelect, { Label } from "./SourceMachineSelect";

import type { Machine } from "@/app/store/machine/types";
import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("SourceMachineSelect", () => {
  let machines: Machine[];
  let state: RootState;

  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValueOnce("123456");
    machines = [
      factory.machine({
        system_id: "abc123",
        hostname: "first",
        owner: "admin",
        tags: [12],
      }),
      factory.machine({
        system_id: "def456",
        hostname: "second",
        owner: "user",
        tags: [13],
      }),
    ];
    state = factory.rootState({
      machine: factory.machineState({
        items: machines,
        lists: {
          "123456": factory.machineStateList({
            groups: [
              factory.machineStateListGroup({
                items: machines.map(({ system_id }) => system_id),
              }),
            ],
            loaded: true,
          }),
        },
        loaded: true,
      }),
      tag: factory.tagState({
        items: [
          factory.tag({ id: 12, name: "tagA" }),
          factory.tag({ id: 13, name: "tagB" }),
        ],
      }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows an error if no machines are available to select", () => {
    state.machine.lists["123456"] = factory.machineStateList({
      loaded: true,
      loading: false,
      count: 0,
    });
    renderWithProviders(<SourceMachineSelect onMachineClick={vi.fn()} />, {
      state,
    });
    expect(screen.getByText(Label.NoSourceMachines)).toBeInTheDocument();
  });

  it("does not show an error if machines are available to select", () => {
    renderWithProviders(<SourceMachineSelect onMachineClick={vi.fn()} />, {
      state,
    });
    expect(
      screen.queryByRole("heading", { name: Label.NoSourceMachines })
    ).not.toBeInTheDocument();
  });

  it("shows the machine's details when selected", () => {
    const selectedMachine = factory.machineDetails();

    renderWithProviders(
      <SourceMachineSelect
        onMachineClick={vi.fn()}
        selectedMachine={selectedMachine}
      />,
      { state }
    );

    expect(
      screen.getByLabelText(SourceMachineDetailsLabel.Title)
    ).toBeInTheDocument();
  });

  it("clears the selected machine on search input change", async () => {
    const selectedMachine = factory.machineDetails();
    const onMachineClick = vi.fn();

    renderWithProviders(
      <SourceMachineSelect
        onMachineClick={onMachineClick}
        selectedMachine={selectedMachine}
      />,
      { state }
    );

    await userEvent.type(
      screen.getByRole("combobox", { name: /Search/i }),
      " "
    );
    expect(onMachineClick).toHaveBeenCalledWith(null);
  });
});
