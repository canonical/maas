import GroupSelect from "./GroupSelect";

import { groupOptions } from "@/app/machines/constants";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

it("executes setGrouping and setHiddenGroups functions on change", async () => {
  const setGrouping = vi.fn();
  const setHiddenGroups = vi.fn();
  renderWithProviders(
    <GroupSelect
      groupOptions={groupOptions}
      grouping={null}
      setGrouping={setGrouping}
      setHiddenGroups={setHiddenGroups}
    />
  );
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Group by" }),
    "status"
  );
  expect(setGrouping).toHaveBeenCalledWith("status");
  expect(setHiddenGroups).toHaveBeenCalledWith([]);
});
