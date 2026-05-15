import SubnetUsedIPs from "./SubnetUsedIPs";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

it("displays correct IP addresses", () => {
  const subnet = factory.subnetDetails({
    ip_addresses: [
      factory.subnetIP({
        ip: "11.1.1.1",
        alloc_type: 4,
      }),
      factory.subnetIP({
        ip: "11.1.1.2",
        alloc_type: 5,
      }),
    ],
  });
  const state = factory.rootState({
    subnet: factory.subnetState({
      items: [subnet],
    }),
  });

  renderWithProviders(<SubnetUsedIPs subnetId={subnet.id} />, { state });

  expect(screen.getByRole("row", { name: /^11.1.1.1/ }));
  expect(screen.getByRole("row", { name: /^11.1.1.2/ }));
});

it("displays an empty message for a subnet", () => {
  const subnet = factory.subnetDetails({
    ip_addresses: [],
  });
  const state = factory.rootState({
    subnet: factory.subnetState({
      items: [subnet],
    }),
  });

  renderWithProviders(<SubnetUsedIPs subnetId={subnet.id} />, { state });

  expect(
    screen.getByText("No IP addresses for this subnet.")
  ).toBeInTheDocument();
});
