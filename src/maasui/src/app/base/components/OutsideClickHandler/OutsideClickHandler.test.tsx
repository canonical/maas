import OutsideClickHandler from "./OutsideClickHandler";

import { userEvent, screen, renderWithProviders } from "@/testing/utils";

it("calls the onClick handler when clicking outside of the component", async () => {
  const onClick = vi.fn();
  renderWithProviders(
    <div>
      <div>Outside</div>
      <OutsideClickHandler onClick={onClick}>
        <div>Inside</div>
      </OutsideClickHandler>
    </div>
  );
  await userEvent.click(screen.getByText("Inside"));
  expect(onClick).not.toHaveBeenCalled();
  await userEvent.click(screen.getByText("Outside"));
  expect(onClick).toHaveBeenCalled();
});
