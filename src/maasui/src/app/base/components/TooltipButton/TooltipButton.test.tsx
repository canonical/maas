import TooltipButton from "./TooltipButton";

import { breakLines, unindentString } from "@/app/utils";
import {
  userEvent,
  screen,
  within,
  renderWithProviders,
} from "@/testing/utils";

it("renders with default options correctly", async () => {
  renderWithProviders(
    <TooltipButton data-testid="tooltip-portal" message="Tooltip" />
  );
  const button = screen.getByRole("button");

  await userEvent.click(button);

  expect(screen.getByRole("tooltip")).toHaveTextContent("Tooltip");
  expect(within(button).getByLabelText("information")).toHaveClass(
    "p-icon--information"
  );
});

it("can override default props", async () => {
  renderWithProviders(
    <TooltipButton
      buttonProps={{ appearance: "negative", className: "button-class" }}
      data-testid="tooltip-portal"
      iconName="warning"
      iconProps={{ className: "icon-class" }}
      message="Tooltip"
      tooltipClassName="tooltip-class"
    />
  );
  const button = screen.getByRole("button");

  expect(button).toHaveClass("p-button--negative");
  expect(button).toHaveClass("button-class");
  expect(within(button).getByLabelText("warning")).toHaveClass(
    "p-icon--warning"
  );
  expect(within(button).getByLabelText("warning")).toHaveClass("icon-class");

  await userEvent.click(button);

  expect(screen.getByTestId("tooltip-portal")).toHaveClass("tooltip-class");
});

it("automatically unindents and breaks string messages into lines", async () => {
  const message = `Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed
  a malesuada leo. Cras imperdiet maximus velit vel euismod. Fusce laoreet sem
  at pellentesque ultricies. Proin posuere tortor at sollicitudin tempus.`;
  renderWithProviders(<TooltipButton message={message} />);
  const button = screen.getByRole("button");

  await userEvent.click(button);

  expect(screen.getByRole("tooltip").textContent).toBe(
    breakLines(unindentString(message))
  );
});
