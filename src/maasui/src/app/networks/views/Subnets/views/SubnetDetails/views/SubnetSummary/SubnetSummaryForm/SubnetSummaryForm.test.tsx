import SubnetSummaryForm from "./SubnetSummaryForm";

import { subnetActions } from "@/app/store/subnet";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

it("can dispatch an action to update the subnet", async () => {
  const fabrics = [
    factory.fabric({ default_vlan_id: 3, id: 1, vlan_ids: [3] }),
    factory.fabric({ default_vlan_id: 4, id: 2, vlan_ids: [4] }),
  ];
  const vlans = [
    factory.vlan({ fabric: 1, id: 3 }),
    factory.vlan({ fabric: 2, id: 4 }),
  ];
  const subnet = factory.subnet({
    active_discovery: false,
    allow_dns: false,
    allow_proxy: false,
    cidr: "192.168.1.0/24",
    description: "I'm a subnet",
    dns_servers: "abcde",
    gateway_ip: "192.168.1.1",
    managed: false,
    name: "Old Name",
    id: 5,
    vlan: vlans[0].id,
  });
  const state = factory.rootState({
    fabric: factory.fabricState({ items: fabrics, loaded: true }),
    subnet: factory.subnetState({ items: [subnet], loaded: true }),
    vlan: factory.vlanState({ items: vlans, loaded: true }),
  });
  const { store } = renderWithProviders(
    <SubnetSummaryForm handleDismiss={vi.fn()} id={subnet.id} />,
    { state }
  );
  const cidrField = screen.getByRole("textbox", { name: "CIDR" });
  const nameField = screen.getByRole("textbox", { name: "Name" });
  const descriptionField = screen.getByRole("textbox", { name: "Description" });
  const gatewayIpField = screen.getByRole("textbox", { name: "Gateway IP" });
  const dnsField = screen.getByRole("textbox", { name: "DNS" });

  await userEvent.clear(cidrField);
  await userEvent.type(cidrField, "192.168.2.0/24");
  await userEvent.clear(nameField);
  await userEvent.type(nameField, "New Name");
  await userEvent.clear(descriptionField);
  await userEvent.type(descriptionField, "I'm a supernet");
  await userEvent.clear(gatewayIpField);
  await userEvent.type(gatewayIpField, "192.168.2.1");
  await userEvent.clear(dnsField);
  await userEvent.type(dnsField, "fghij");
  await userEvent.click(
    screen.getByRole("checkbox", { name: /Managed allocation/i })
  );
  await userEvent.click(
    screen.getByRole("checkbox", { name: /Active discovery/i })
  );
  await userEvent.click(
    screen.getByRole("checkbox", { name: /Allow DNS resolution/i })
  );
  await userEvent.click(
    screen.getByRole("checkbox", { name: /Proxy access/i })
  );
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Fabric" }),
    fabrics[1].id.toString()
  );

  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "VLAN" }),
    vlans[1].id.toString()
  );
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  const expectedAction = subnetActions.update({
    active_discovery: true,
    allow_dns: true,
    allow_proxy: true,
    cidr: "192.168.2.0/24",
    description: "I'm a supernet",
    dns_servers: "fghij",
    gateway_ip: "192.168.2.1",
    id: subnet.id,
    managed: true,
    name: "New Name",
    vlan: vlans[1].id,
  });
  const actualActions = store.getActions();

  await waitFor(() => {
    expect(
      actualActions.find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });
});
