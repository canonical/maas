import MachineNotifications from "./MachineNotifications";

import { screen, renderWithProviders } from "@/testing/utils";

it("ignores inactive notifications", () => {
  renderWithProviders(
    <MachineNotifications
      notifications={[
        {
          active: false,
          content: "Don't show me!",
          severity: "negative",
          title: "Error:",
        },
        {
          active: true,
          content: "Show me!",
          severity: "negative",
          title: "Error:",
        },
        {
          active: true,
          content: "Show me!",
          severity: "negative",
          title: "Error:",
        },
      ]}
    />
  );
  expect(screen.queryAllByRole("alert").length).toEqual(2);
});

it("adds an 'alert' role to notifications with 'negative' severity", () => {
  renderWithProviders(
    <MachineNotifications
      notifications={[
        {
          active: true,
          content: "Show me!",
          severity: "negative",
          title: "Error:",
        },
      ]}
    />
  );
  expect(screen.getByRole("alert")).toBeInTheDocument();
});

it("adds a 'status' role to notifications with 'caution', 'information' and 'positive' severity", () => {
  renderWithProviders(
    <MachineNotifications
      notifications={[
        {
          active: true,
          content: "Notification with caution severity",
          severity: "caution",
        },
        {
          active: true,
          content: "Notification with information severity",
          severity: "information",
        },
        {
          active: true,
          content: "Notification with positive severity",
          severity: "positive",
        },
      ]}
    />
  );
  expect(screen.queryAllByRole("status").length).toEqual(3);
});
