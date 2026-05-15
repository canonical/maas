import EditDisk from "./EditDisk";

import type { RootState } from "@/app/store/root/types";
import { DiskTypes } from "@/app/store/types/enum";
import type { Disk } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("EditDisk", () => {
  let state: RootState;
  let disk: Disk;

  beforeEach(() => {
    disk = factory.nodeDisk({
      is_boot: false,
      type: DiskTypes.PHYSICAL,
    });
    state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            disks: [disk],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
  });

  it("shows filesystem fields if the disk is not the boot disk", () => {
    renderWithProviders(<EditDisk disk={disk} systemId="abc123" />, {
      state,
    });

    expect(screen.getByRole("textbox", { name: "Name" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Type" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Size" })).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Filesystem" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: "Mount point" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: "Mount options" })
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Tags" })).toBeInTheDocument();
  });

  it("correctly dispatches an action to edit a disk", async () => {
    disk.is_boot = true;
    state.machine.items = [
      factory.machineDetails({
        disks: [disk],
        system_id: "abc123",
      }),
    ];
    const { store } = renderWithProviders(
      <EditDisk disk={disk} systemId="abc123" />,
      {
        state,
      }
    );

    await userEvent.type(screen.getByRole("textbox", { name: "Tags" }), "tag1");
    await userEvent.click(screen.getByTestId("new-tag"));
    await userEvent.click(screen.getByRole("button", { name: /Save/i }));

    expect(
      store.getActions().find((action) => action.type === "machine/updateDisk")
    ).toStrictEqual({
      meta: {
        method: "update_disk",
        model: "machine",
      },
      payload: {
        params: {
          block_id: disk.id,
          system_id: "abc123",
          tags: ["tag1"],
        },
      },
      type: "machine/updateDisk",
    });
  });
});
