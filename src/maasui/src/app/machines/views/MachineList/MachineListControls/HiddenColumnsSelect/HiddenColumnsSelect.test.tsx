import HiddenColumnsSelect from "./HiddenColumnsSelect";

import { columnToggles } from "@/app/machines/constants";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

it("calls setHiddenColumns correctly on click of a checkbox", async () => {
  const hiddenColumns: ""[] = [];
  const setHiddenColumns = vi.fn();
  renderWithProviders(
    <HiddenColumnsSelect
      hiddenColumns={hiddenColumns}
      setHiddenColumns={setHiddenColumns}
    />
  );
  await userEvent.click(screen.getByRole("button", { name: "Columns" }));
  expect(
    screen.getByRole("checkbox", { name: /10 out of 10 selected/ })
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("checkbox", { name: "RAM" }));
  expect(setHiddenColumns).toHaveBeenCalledWith(["memory"]);
});

it("displays a correct number of selected columns", async () => {
  const hiddenColumns = ["memory"];
  const setHiddenColumns = vi.fn();
  renderWithProviders(
    <HiddenColumnsSelect
      hiddenColumns={hiddenColumns}
      setHiddenColumns={setHiddenColumns}
    />
  );
  await userEvent.click(screen.getByRole("button", { name: "Columns" }));
  expect(
    screen.getByRole("checkbox", { name: /9 out of 10 selected/ })
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("checkbox", { name: "RAM" }));
  expect(setHiddenColumns).toHaveBeenCalledWith([]);
});

it("group checkbox selects all columns on press", async () => {
  const hiddenColumns: string[] = [];
  const setHiddenColumns = vi.fn();
  renderWithProviders(
    <HiddenColumnsSelect
      hiddenColumns={hiddenColumns}
      setHiddenColumns={setHiddenColumns}
    />
  );
  await userEvent.click(screen.getByRole("button", { name: "Columns" }));
  await userEvent.click(
    screen.getByRole("checkbox", { name: /10 out of 10 selected/ })
  );
  expect(setHiddenColumns).toHaveBeenCalledWith([...columnToggles]);
});
