import VirshTable from "./VirshTable";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { mockPools, poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitForLoading,
  within,
} from "@/testing/utils";

setupMockServer(
  poolsResolvers.listPools.handler(),
  poolsResolvers.getPool.handler(),
  zoneResolvers.getZone.handler()
);

describe("VirshTable", () => {
  let state: RootState;
  let pods = [
    factory.pod({ pool: 1, zone: 1 }),
    factory.pod({ pool: 2, zone: 2 }),
  ];
  beforeEach(() => {
    pods = [
      factory.pod({ pool: 1, zone: 1 }),
      factory.pod({ pool: 2, zone: 2 }),
    ];
    state = factory.rootState({
      pod: factory.podState({ items: pods, loaded: true }),
    });
  });

  describe("display", () => {
    it("shows pods sorted by descending name by default", async () => {
      state.pod.items[0].name = "a";
      state.pod.items[1].name = "b";
      renderWithProviders(<VirshTable />, {
        initialEntries: ["/kvm"],
        state,
      });
      await waitForLoading();

      const rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole(
        "row"
      );
      expect(within(rows[0]).getAllByRole("cell")[0]).toHaveTextContent(/b/i);
      expect(within(rows[1]).getAllByRole("cell")[0]).toHaveTextContent(/a/i);
    });

    it("displays a message when empty", () => {
      state.pod.items = [];
      renderWithProviders(<VirshTable />, {
        initialEntries: ["/kvm"],
        state,
      });

      expect(screen.getByText("No pods available.")).toBeInTheDocument();
    });
  });
  describe("actions", () => {
    it("can sort by parameters of the pods themselves", async () => {
      state.pod.items[0].name = "a";
      state.pod.items[1].name = "b";
      state.pod.items[0].resources.vm_count.tracked = 1;
      state.pod.items[1].resources.vm_count.tracked = 2;
      renderWithProviders(<VirshTable />, {
        initialEntries: ["/kvm"],
        state,
      });
      await waitForLoading();

      let rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");
      expect(within(rows[0]).getAllByRole("cell")[0]).toHaveTextContent(/b/i);
      expect(within(rows[1]).getAllByRole("cell")[0]).toHaveTextContent(/a/i);

      await userEvent.click(screen.getByRole("button", { name: /name/i }));
      rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");
      expect(within(rows[0]).getAllByRole("cell")[0]).toHaveTextContent(/a/i);
      expect(within(rows[1]).getAllByRole("cell")[0]).toHaveTextContent(/b/i);

      // Click the VMs table header to order by descending VMs count
      await userEvent.click(screen.getByRole("button", { name: /VMs/i }));
      rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");

      expect(within(rows[0]).getAllByRole("cell")[1]).toHaveTextContent(/2/i);
      expect(within(rows[1]).getAllByRole("cell")[1]).toHaveTextContent(/1/i);

      await userEvent.click(screen.getByRole("button", { name: /VMs/i }));
      rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");

      expect(within(rows[0]).getAllByRole("cell")[1]).toHaveTextContent(/1/i);
      expect(within(rows[1]).getAllByRole("cell")[1]).toHaveTextContent(/2/i);
    });

    it("can sort by pod resource pool", async () => {
      const [firstPod, secondPod] = [state.pod.items[0], state.pod.items[1]];
      firstPod.pool = mockPools.items[0].id;
      secondPod.pool = mockPools.items[1].id;
      firstPod.name = "a";
      secondPod.name = "b";
      renderWithProviders(<VirshTable />, {
        initialEntries: ["/kvm"],
        state,
      });
      await waitForLoading();

      let rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");
      expect(within(rows[0]).getAllByRole("cell")[0]).toHaveTextContent(/b/i);
      expect(within(rows[1]).getAllByRole("cell")[0]).toHaveTextContent(/a/i);

      await userEvent.click(
        screen.getByRole("button", { name: /Resource Pool/i })
      );

      rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");
      expect(within(rows[0]).getAllByRole("cell")[3]).toHaveTextContent(
        /gene/i
      );
      expect(within(rows[1]).getAllByRole("cell")[3]).toHaveTextContent(
        /swimming/i
      );

      await userEvent.click(
        screen.getByRole("button", { name: /Resource Pool/i })
      );
      rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");
      expect(within(rows[0]).getAllByRole("cell")[3]).toHaveTextContent(
        /swimming/i
      );
      expect(within(rows[1]).getAllByRole("cell")[3]).toHaveTextContent(
        /gene/i
      );
    });
  });
});
