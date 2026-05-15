import type { MockedFunction } from "vitest";

import GroupColumn from "./GroupColumn";

import { FetchGroupKey } from "@/app/store/machine/types";
import { useFetchMachineCount } from "@/app/store/machine/utils/hooks";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, waitFor } from "@/testing/utils";

vi.mock("@/app/store/machine/utils/hooks");

const mockedUseFetchMachineCount = useFetchMachineCount as MockedFunction<
  typeof useFetchMachineCount
>;
mockedUseFetchMachineCount.mockReturnValue({
  machineCountLoading: false,
  machineCountLoaded: true,
  machineCount: 2,
});

it("displays the correct column name and machines count", () => {
  const group = factory.machineStateListGroup({
    collapsed: false,
    count: 5,
    name: "Test Group",
    value: "test-group",
  });
  renderWithProviders(
    <GroupColumn
      callId="test-call-id"
      filter={null}
      group={group}
      grouping={FetchGroupKey.Status}
      hiddenGroups={[null]}
      setHiddenGroups={vi.fn()}
      showActions={false}
    />
  );

  expect(screen.getByText(/Test Group/)).toBeInTheDocument();
  expect(screen.getByText(/5 machines/)).toBeInTheDocument();
});

it("displays correct fetched machines count when initial count is null", async () => {
  const group = factory.machineStateListGroup({
    collapsed: false,
    count: null,
    name: "Test Group",
    value: "test-group",
  });

  renderWithProviders(
    <GroupColumn
      callId="test-call-id"
      filter={null}
      group={group}
      grouping={FetchGroupKey.Status}
      hiddenGroups={[null]}
      setHiddenGroups={vi.fn()}
      showActions={false}
    />
  );

  expect(screen.getByText(/Test Group/)).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.getByText(/2 machines/)).toBeInTheDocument();
  });
});
