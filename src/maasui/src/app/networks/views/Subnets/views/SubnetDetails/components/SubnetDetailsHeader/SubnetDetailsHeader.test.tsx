import SubnetDetailsHeader from "./SubnetDetailsHeader";

import * as factory from "@/testing/factories";
import { userEvent, renderWithProviders, screen } from "@/testing/utils";

it("shows the subnet name as the section title", () => {
  const subnet = factory.subnet({ id: 1, name: "subnet-1" });
  renderWithProviders(<SubnetDetailsHeader subnet={subnet} />);

  expect(screen.getByTestId("section-header-title")).toHaveTextContent(
    "subnet-1"
  );
});

it("shows a spinner subtitle if the subnet is loading details", () => {
  const subnet = factory.subnet({ id: 1, name: "subnet-1" });
  renderWithProviders(<SubnetDetailsHeader subnet={subnet} />);

  expect(
    screen.getByTestId("section-header-subtitle-spinner")
  ).toBeInTheDocument();
});

it("does not show a spinner subtitle if the subnet is detailed", () => {
  const subnet = factory.subnetDetails({ id: 1, name: "subnet-1" });
  renderWithProviders(<SubnetDetailsHeader subnet={subnet} />);

  expect(screen.queryByTestId("section-header-subtitle-spinner")).toBeNull();
});

it("displays available actions", async () => {
  const subnet = factory.subnetDetails({ id: 1, name: "subnet-1" });
  renderWithProviders(<SubnetDetailsHeader subnet={subnet} />);

  ["Map subnet", "Edit boot architectures", "Delete subnet"].forEach((name) => {
    expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
  });

  await userEvent.click(screen.getByRole("button", { name: "Take action" }));

  ["Map subnet", "Edit boot architectures", "Delete subnet"].forEach((name) => {
    expect(screen.getByRole("button", { name })).toBeInTheDocument();
  });
});
