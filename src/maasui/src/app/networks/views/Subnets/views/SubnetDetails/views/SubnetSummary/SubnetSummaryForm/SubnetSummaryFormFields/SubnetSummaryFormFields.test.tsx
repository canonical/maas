import { Formik } from "formik";

import SubnetSummaryFormFields from "./SubnetSummaryFormFields";

import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

it("updates to use the fabric's default VLAN on fabric change", async () => {
  const fabrics = [
    factory.fabric({ default_vlan_id: 3, id: 1, vlan_ids: [3] }),
    factory.fabric({ default_vlan_id: 5, id: 2, vlan_ids: [4, 5] }),
  ];
  const vlans = [
    factory.vlan({ fabric: 1, id: 3 }),
    factory.vlan({ fabric: 2, id: 4 }),
    factory.vlan({ fabric: 2, id: 5 }),
  ];
  const state = factory.rootState({
    fabric: factory.fabricState({ items: fabrics, loaded: true }),
    vlan: factory.vlanState({ items: vlans, loaded: true }),
  });
  renderWithProviders(
    <Formik initialValues={{ fabric: 1, vlan: 3 }} onSubmit={vi.fn()}>
      <SubnetSummaryFormFields />
    </Formik>,
    { state }
  );

  expect(screen.getByRole("combobox", { name: "VLAN" })).toHaveValue("3");

  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Fabric" }),
    fabrics[1].id.toString()
  );

  await waitFor(() => {
    expect(screen.getByRole("combobox", { name: "VLAN" })).toHaveValue("5");
  });
});
