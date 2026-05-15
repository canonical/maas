import ErrorsNotification from "./ErrorsNotification";

import {
  userEvent,
  screen,
  render,
  renderWithProviders,
} from "@/testing/utils";

it("can display and close an error message", async () => {
  renderWithProviders(
    <ErrorsNotification errors={{ title: "error message" }} />
  );
  expect(screen.getByText("title: error message")).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Close notification" })
  );
  expect(screen.queryByText("title: error message")).not.toBeInTheDocument();
});

it("reopens the notification with a new error when previously dismissed", async () => {
  const { rerender } = render(
    <ErrorsNotification errors={{ title: "error message" }} />
  );
  expect(screen.getByText("title: error message")).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Close notification" })
  );
  expect(screen.queryByText("title: error message")).not.toBeInTheDocument();
  rerender(<ErrorsNotification errors={{ title: "another error message" }} />);
  expect(screen.getByText("title: another error message")).toBeInTheDocument();
});
