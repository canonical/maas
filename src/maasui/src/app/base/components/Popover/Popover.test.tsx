import Popover from "./Popover";

import { screen, userEvent, renderWithProviders } from "@/testing/utils";

it("renders popover content when focused", async () => {
  renderWithProviders(
    <Popover content={<span>popover content</span>}>child text</Popover>
  );
  expect(screen.queryByText("popover content")).not.toBeInTheDocument();
  await userEvent.click(screen.getByText("child text"));
  expect(screen.getByText("popover content")).toBeInTheDocument();
});

it("keeps popover content open on unhover if initiated by click", async () => {
  renderWithProviders(
    <Popover content={<span>popover content</span>}>trigger</Popover>
  );
  const button = screen.getByRole("button", { name: "trigger" });
  await userEvent.hover(button);
  expect(screen.getByText("popover content")).toBeInTheDocument();
  await userEvent.unhover(button);
  expect(screen.queryByText("popover content")).not.toBeInTheDocument();
  await userEvent.click(button);
  expect(screen.getByText("popover content")).toBeInTheDocument();
  await userEvent.unhover(button);
  expect(screen.getByText("popover content")).toBeInTheDocument();
});
