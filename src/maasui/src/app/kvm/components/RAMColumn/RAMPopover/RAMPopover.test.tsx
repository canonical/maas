import RAMPopover from "./RAMPopover";

import * as factory from "@/testing/factories";
import { fireEvent, screen, renderWithProviders } from "@/testing/utils";

describe("RAMPopover", () => {
  it("shows if memory is used by any other projects in the group", () => {
    renderWithProviders(
      <RAMPopover
        memory={factory.podMemoryResource({
          general: factory.podResource({
            allocated_other: 1,
          }),
          hugepages: factory.podResource({
            allocated_other: 1,
          }),
        })}
        overCommit={1}
      >
        Child
      </RAMPopover>
    );

    fireEvent.focus(screen.getByRole("button", { name: /child/i }));
    expect(screen.getByTestId("other")).toBeInTheDocument();
  });

  it("does not show other memory if no other projects in the group use them", () => {
    renderWithProviders(
      <RAMPopover
        memory={factory.podMemoryResource({
          general: factory.podResource({ allocated_other: 0 }),
          hugepages: factory.podResource({ allocated_other: 0 }),
        })}
        overCommit={1}
      >
        Child
      </RAMPopover>
    );

    fireEvent.focus(screen.getByRole("button", { name: /child/i }));
    expect(screen.queryByTestId("other")).not.toBeInTheDocument();
  });

  it("shows memory over-commit ratio if it is not equal to 1", () => {
    renderWithProviders(
      <RAMPopover memory={factory.podMemoryResource()} overCommit={2}>
        Child
      </RAMPopover>
    );

    fireEvent.focus(screen.getByRole("button", { name: /child/i }));
    expect(screen.getByTestId("overcommit")).toBeInTheDocument();
  });

  it("does not show memory over-commit ratio if it is equal to 1", () => {
    renderWithProviders(
      <RAMPopover memory={factory.podMemoryResource()} overCommit={1}>
        Child
      </RAMPopover>
    );
    fireEvent.focus(screen.getByRole("button", { name: /child/i }));
    expect(screen.queryByTestId("overcommit")).not.toBeInTheDocument();
  });

  it("displays memory for a vmcluster", () => {
    const memory = factory.vmClusterResourcesMemory({
      general: factory.vmClusterResource({
        allocated_other: 1,
        allocated_tracked: 2,
        free: 3,
      }),
      hugepages: factory.vmClusterResource({
        allocated_other: 4,
        allocated_tracked: 5,
        free: 6,
      }),
    });
    renderWithProviders(<RAMPopover memory={memory}>Child</RAMPopover>);

    fireEvent.focus(screen.getByRole("button", { name: /child/i }));
    expect(screen.getByTestId("other")).toHaveTextContent("5B");
    expect(screen.getByTestId("allocated")).toHaveTextContent("7B");
    expect(screen.getByTestId("free")).toHaveTextContent("9B");
    expect(screen.getByTestId("total")).toHaveTextContent("21B");
  });
});
