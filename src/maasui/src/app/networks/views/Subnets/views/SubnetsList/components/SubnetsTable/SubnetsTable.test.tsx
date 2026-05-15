import SubnetsTable from "./SubnetsTable";
import { SUBNETS_TABLE_ITEMS_PER_PAGE } from "./constants";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

const getMockState = ({ numberOfSubnets } = { numberOfSubnets: 50 }) => {
  const subnets = [
    ...new Array(numberOfSubnets)
      .fill(null)
      .map((_value, index) => factory.subnet({ id: index + 1, vlan: 1 })),
  ];
  return factory.rootState({
    fabric: factory.fabricState({
      loaded: true,
      items: [factory.fabric({ id: 1, name: "fabric-1" })],
    }),
    vlan: factory.vlanState({
      loaded: true,
      items: [factory.vlan({ id: 1, fabric: 1 })],
    }),
    subnet: factory.subnetState({ loaded: true, items: subnets }),
    space: factory.spaceState({ loaded: true }),
  });
};

describe("SubnetsTable", () => {
  describe("display", () => {
    it("renders Subnets by Fabric table when grouping by Fabric", () => {
      const state = getMockState();

      renderWithProviders(<SubnetsTable groupBy="fabric" searchText="" />, {
        state,
      });

      expect(
        screen.getByRole("grid", { name: "Subnets by fabric" })
      ).toBeInTheDocument();

      const firstRow = within(screen.getAllByRole("rowgroup")[1]).getAllByRole(
        "row"
      )[0];

      expect(within(firstRow).getByRole("link")).toHaveTextContent("fabric-1");
    });

    it("renders Subnets by Space table when grouping by Space", () => {
      const state = getMockState();

      renderWithProviders(<SubnetsTable groupBy="space" searchText="" />, {
        state,
      });

      expect(
        screen.getByRole("grid", { name: "Subnets by space" })
      ).toBeInTheDocument();
    });

    it("hides the space column when grouping by space", () => {
      const state = getMockState();

      renderWithProviders(<SubnetsTable groupBy="space" searchText="" />, {
        state,
      });

      expect(
        screen.getByRole("grid", { name: "Subnets by space" })
      ).toBeInTheDocument();

      expect(
        screen.queryByRole("columnheader", { name: /space/i })
      ).not.toBeInTheDocument();
    });

    it("hides the fabric column when grouping by fabric", () => {
      const state = getMockState();

      renderWithProviders(<SubnetsTable groupBy="fabric" searchText="" />, {
        state,
      });

      expect(
        screen.getByRole("grid", { name: "Subnets by fabric" })
      ).toBeInTheDocument();

      expect(
        screen.queryByRole("columnheader", { name: /fabric/i })
      ).not.toBeInTheDocument();
    });
  });

  describe("search and filter", () => {
    it("can match search text to subnet names", () => {
      const state = factory.rootState({
        fabric: factory.fabricState({
          loaded: true,
          items: [factory.fabric({ id: 1, name: "giraffe" })],
        }),
        vlan: factory.vlanState({
          loaded: true,
          items: [factory.vlan({ id: 1, fabric: 1 })],
        }),
        subnet: factory.subnetState({
          loaded: true,
          items: [
            factory.subnet({
              name: "springbok",
              vlan: 1,
            }),
            factory.subnet({
              name: "kudu",
              vlan: 1,
            }),
            factory.subnet({
              name: "impala",
              vlan: 1,
            }),
          ],
        }),
        space: factory.spaceState({ loaded: true }),
      });

      renderWithProviders(<SubnetsTable groupBy="fabric" searchText="kudu" />, {
        state,
      });

      expect(screen.getByText(/kudu/i)).toBeInTheDocument();

      expect(screen.queryByText(/springbok/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/impala/i)).not.toBeInTheDocument();
    });

    it("can match search text to vlan names", () => {
      const state = factory.rootState({
        fabric: factory.fabricState({
          loaded: true,
          items: [factory.fabric({ id: 1, name: "giraffe" })],
        }),
        vlan: factory.vlanState({
          loaded: true,
          items: [
            factory.vlan({ id: 1, fabric: 1, name: "wildebeest" }),
            factory.vlan({ id: 2, fabric: 1, name: "elephant" }),
          ],
        }),
        subnet: factory.subnetState({
          loaded: true,
          items: [
            factory.subnet({
              name: "springbok",
              vlan: 1,
            }),
            factory.subnet({
              name: "kudu",
              vlan: 1,
            }),
            factory.subnet({
              name: "impala",
              vlan: 2,
            }),
          ],
        }),
        space: factory.spaceState({ loaded: true }),
      });

      renderWithProviders(
        <SubnetsTable groupBy="fabric" searchText="wildebeest" />,
        {
          state,
        }
      );

      // two subnets are in this vlan, so the name should appear twice
      expect(screen.getAllByText(/wildebeest/i)).toHaveLength(2);
      expect(screen.getByText(/springbok/i)).toBeInTheDocument();
      expect(screen.getByText(/kudu/i)).toBeInTheDocument();

      expect(screen.queryByText(/elephant/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/impala/i)).not.toBeInTheDocument();
    });

    it("can match search text to fabric names", () => {
      const state = factory.rootState({
        fabric: factory.fabricState({
          loaded: true,
          items: [
            factory.fabric({ id: 1, name: "giraffe" }),
            factory.fabric({ id: 2, name: "buffalo" }),
          ],
        }),
        vlan: factory.vlanState({
          loaded: true,
          items: [
            factory.vlan({ id: 1, fabric: 1, name: "wildebeest" }),
            factory.vlan({ id: 2, fabric: 2, name: "elephant" }),
          ],
        }),
        subnet: factory.subnetState({
          loaded: true,
          items: [
            factory.subnet({
              name: "springbok",
              vlan: 1,
            }),
            factory.subnet({
              name: "kudu",
              vlan: 1,
            }),
            factory.subnet({
              name: "impala",
              vlan: 2,
            }),
          ],
        }),
        space: factory.spaceState({ loaded: true }),
      });

      renderWithProviders(
        <SubnetsTable groupBy="fabric" searchText="buffalo" />,
        {
          state,
        }
      );

      expect(screen.getByText(/buffalo/i)).toBeInTheDocument();
      expect(screen.getByText(/elephant/i)).toBeInTheDocument();
      expect(screen.getByText(/impala/i)).toBeInTheDocument();

      expect(screen.queryByText(/giraffe/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/kudu/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/springbok/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/wildebeest/i)).not.toBeInTheDocument();
    });

    it("can match search text to space names", () => {
      const state = factory.rootState({
        fabric: factory.fabricState({
          loaded: true,
          items: [
            factory.fabric({ id: 1, name: "giraffe" }),
            factory.fabric({ id: 2, name: "buffalo" }),
          ],
        }),
        vlan: factory.vlanState({
          loaded: true,
          items: [
            factory.vlan({ id: 1, fabric: 1, name: "wildebeest" }),
            factory.vlan({ id: 2, fabric: 2, name: "elephant" }),
          ],
        }),
        subnet: factory.subnetState({
          loaded: true,
          items: [
            factory.subnet({
              name: "springbok",
              vlan: 1,
              space: 1,
            }),
            factory.subnet({
              name: "kudu",
              vlan: 1,
              space: 2,
            }),
            factory.subnet({
              name: "impala",
              vlan: 2,
              space: 2,
            }),
          ],
        }),
        space: factory.spaceState({
          loaded: true,
          items: [
            factory.space({ id: 1, name: "lion" }),
            factory.space({ id: 2, name: "leopard" }),
          ],
        }),
      });

      renderWithProviders(<SubnetsTable groupBy="fabric" searchText="lion" />, {
        state,
      });

      expect(screen.getByText(/lion/i)).toBeInTheDocument();
      expect(screen.getByText(/springbok/i)).toBeInTheDocument();
      expect(screen.getByText(/wildebeest/i)).toBeInTheDocument();
      expect(screen.getByText(/giraffe/i)).toBeInTheDocument();

      expect(screen.queryByText(/buffalo/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/elephant/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/kudu/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/impala/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/leopard/i)).not.toBeInTheDocument();
    });
  });
});

it("displays a correct number of pages", () => {
  const state = getMockState();

  renderWithProviders(<SubnetsTable groupBy="fabric" searchText="" />, {
    state,
  });

  expect(
    screen.getByRole("grid", { name: "Subnets by fabric" })
  ).toBeInTheDocument();

  const numberOfPages = Math.ceil(
    state.subnet.items.length / SUBNETS_TABLE_ITEMS_PER_PAGE
  );

  expect(
    within(screen.getByRole("navigation", { name: "pagination" })).getByText(
      `of ${numberOfPages}`
    )
  ).toBeInTheDocument();
});
