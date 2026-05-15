import VLANControllers from "./VLANControllers";

import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import type { VLAN } from "@/app/store/vlan/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

let state: RootState;
let vlan: VLAN;

beforeEach(() => {
  const primaryController = factory.controller({
    domain: factory.modelRef({ name: "domain" }),
    hostname: "controller-abc",
    system_id: "abc123",
  });
  const secondaryController = factory.controller({
    domain: factory.modelRef({ name: "domain" }),
    hostname: "controller-def",
    system_id: "def456",
  });
  vlan = factory.vlan({
    primary_rack: primaryController.system_id,
    secondary_rack: secondaryController.system_id,
  });
  state = factory.rootState({
    controller: factory.controllerState({
      items: [primaryController, secondaryController],
    }),
    vlan: factory.vlanState({
      items: [vlan],
    }),
  });
});

it("displays a spinner when loading controllers", () => {
  state.controller.loading = true;
  renderWithProviders(<VLANControllers id={vlan.id} />, { state });
  expect(screen.getByTestId("Spinner")).toBeInTheDocument();
});

it("renders correct details", () => {
  renderWithProviders(<VLANControllers id={vlan.id} />, { state });
  expect(screen.getByRole("link", { name: /controller-abc/i })).toHaveAttribute(
    "href",
    urls.controllers.controller.index({ id: "abc123" })
  );
  expect(screen.getByRole("link", { name: /controller-def/i })).toHaveAttribute(
    "href",
    urls.controllers.controller.index({ id: "def456" })
  );
});
