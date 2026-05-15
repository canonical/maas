import { VLANsColumn } from "./VLANsColumn";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("VLANsColumn", () => {
  const controller = factory.controller({
    system_id: "abc123",
    vlans_ha: factory.controllerVlansHA({
      true: 2,
      false: 1,
    }),
  });

  it("displays total number of vlans", () => {
    renderWithProviders(<VLANsColumn controller={controller} />);
    expect(screen.getByTestId("vlan-count")).toHaveTextContent("3");
  });

  it("displays ha details", () => {
    renderWithProviders(<VLANsColumn controller={controller} />);
    expect(screen.getByTestId("ha-vlans")).toHaveTextContent(
      "Non-HA(1), HA(2)"
    );
  });
});
