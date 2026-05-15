import VLANSubnetsTable from "./VLANSubnetsTable";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

it("renders correct details", () => {
  const vlan = factory.vlan({ id: 5005, subnet_ids: [1] });
  const subnet = factory.subnet({
    allow_dns: true,
    allow_proxy: false,
    managed: true,
    statistics: factory.subnetStatistics({ usage_string: "25%" }),
    vlan: vlan.id,
    id: 1,
  });
  const state = factory.rootState({
    subnet: factory.subnetState({ items: [subnet] }),
    vlan: factory.vlanState({ items: [vlan] }),
  });
  renderWithProviders(<VLANSubnetsTable id={vlan.id} />, { state });
  const vlanSubnetsTable = within(
    screen.getByRole("region", {
      name: "Subnets on this VLAN",
    })
  ).getByRole("grid");

  expect(within(vlanSubnetsTable).getByRole("link")).toHaveAttribute(
    "href",
    urls.networks.subnet.index({ id: subnet.id })
  );
  expect(vlanSubnetsTable.querySelector("td.usage")!.textContent).toBe(
    subnet.statistics.usage_string
  );
  expect(vlanSubnetsTable.querySelector("td.managed")!.textContent).toBe("Yes");
  expect(vlanSubnetsTable.querySelector("td.allow_proxy")!.textContent).toBe(
    "No"
  );
  expect(vlanSubnetsTable.querySelector("td.allow_dns")!.textContent).toBe(
    "Yes"
  );
});
