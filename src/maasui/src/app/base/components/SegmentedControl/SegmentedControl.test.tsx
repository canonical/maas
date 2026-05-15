import SegmentedControl from "./SegmentedControl";

import { screen, userEvent, renderWithProviders } from "@/testing/utils";

const options = [
  {
    label: "Red",
    value: "#FF0000",
  },
  {
    label: "Green",
    value: "#00FF00",
  },
  {
    label: "Blue",
    value: "#0000FF",
  },
];

it("renders a segment for each option", () => {
  renderWithProviders(
    <SegmentedControl onSelect={vi.fn()} options={options} selected="#00FF00" />
  );
  expect(screen.getByRole("tab", { name: "Red" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Green" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Blue" })).toBeInTheDocument();
});

it("selects the active option", () => {
  renderWithProviders(
    <SegmentedControl onSelect={vi.fn()} options={options} selected="#00FF00" />
  );
  expect(screen.getByRole("tab", { name: "Green" })).toHaveAttribute(
    "aria-selected",
    "true"
  );
});

it("calls the callback when clicking a button", async () => {
  const onSelect = vi.fn();
  renderWithProviders(
    <SegmentedControl
      onSelect={onSelect}
      options={options}
      selected="#00FF00"
    />
  );
  await userEvent.click(screen.getByRole("tab", { name: "Blue" }));
  expect(onSelect).toHaveBeenCalledWith("#0000FF");
});
