import FilterAccordion, { Labels } from "./FilterAccordion";
import type { Props as FilterAccordionProps } from "./FilterAccordion";

import type { MachineDetails, MachineMeta } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("FilterAccordion", () => {
  let items: MachineDetails[];
  let filterNames: FilterAccordionProps<
    MachineDetails,
    MachineMeta.PK
  >["filterNames"];
  let filterOrder: string[];
  let getValue: FilterAccordionProps<
    MachineDetails,
    MachineMeta.PK
  >["getValue"];
  beforeEach(() => {
    items = [
      factory.machineDetails({
        link_speeds: [100],
        pool: {
          id: 1,
          name: "pool1",
        },
        pxe_mac: "aa:bb:cc",
        zone: {
          id: 1,
          name: "zone1",
        },
      }),
    ];
    filterNames = new Map([
      ["link_speeds", "Link speed"],
      ["pool", "Resource pool"],
      ["pxe_mac", "PXE Mac"],
      ["zone", "Zone"],
    ]);
    filterOrder = ["pool", "link_speeds", "zone", "pxe_mac"];
    getValue = (machine: MachineDetails, filter: string) => {
      switch (filter) {
        case "pool":
          return machine.pool.name;
        case "zone":
          return machine.zone.name;
        case "link_speeds":
          return machine.link_speeds;
        case "pxe_mac":
          return machine.pxe_mac || null;
        default:
          return null;
      }
    };
  });

  it("can mark an item as active", async () => {
    renderWithProviders(
      <FilterAccordion
        filterNames={filterNames}
        filterOrder={filterOrder}
        filterString="pool:(=pool1)"
        filtersToString={FilterMachines.filtersToString}
        getCurrentFilters={FilterMachines.getCurrentFilters}
        getValue={getValue}
        isFilterActive={FilterMachines.isFilterActive}
        items={items}
        onUpdateFilterString={() => null}
        toggleFilter={FilterMachines.toggleFilter}
      />
    );

    // Open menu and pool filter accordion
    await userEvent.click(screen.getByRole("button", { name: Labels.Toggle }));
    await userEvent.click(
      screen.getByRole("tab", { name: filterNames.get("pool") })
    );

    // Pool 1 should be active due to filterString prop
    expect(
      screen.getByRole("checkbox", { checked: true, name: "pool1 (1)" })
    ).toBeInTheDocument();
  });

  it("can set a filter", async () => {
    const onUpdateFilterString = vi.fn();
    renderWithProviders(
      <FilterAccordion
        filterNames={filterNames}
        filterOrder={filterOrder}
        filterString=""
        filtersToString={FilterMachines.filtersToString}
        getCurrentFilters={FilterMachines.getCurrentFilters}
        getValue={getValue}
        isFilterActive={FilterMachines.isFilterActive}
        items={items}
        onUpdateFilterString={onUpdateFilterString}
        toggleFilter={FilterMachines.toggleFilter}
      />
    );

    // Open menu and pool filter accordion and click pool 1 option
    await userEvent.click(screen.getByRole("button", { name: Labels.Toggle }));
    await userEvent.click(
      screen.getByRole("tab", { name: filterNames.get("pool") })
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "pool1 (1)" }));

    expect(onUpdateFilterString).toHaveBeenCalledWith("pool:(=pool1)");
  });

  it("hides filters if there are no values", async () => {
    delete items[0].pxe_mac;
    renderWithProviders(
      <FilterAccordion
        filterNames={filterNames}
        filterOrder={filterOrder}
        filterString=""
        filtersToString={FilterMachines.filtersToString}
        getCurrentFilters={FilterMachines.getCurrentFilters}
        getValue={getValue}
        isFilterActive={FilterMachines.isFilterActive}
        items={items}
        onUpdateFilterString={() => null}
        toggleFilter={FilterMachines.toggleFilter}
      />
    );

    // Open menu - there shouldn't be an option to filter by PXE mac
    await userEvent.click(screen.getByRole("button", { name: Labels.Toggle }));
    expect(
      screen.queryByRole("tab", { name: filterNames.get("pxe_mac") })
    ).not.toBeInTheDocument();
  });

  it("hides filters if the value is an empty array", async () => {
    items[0].link_speeds = [];
    renderWithProviders(
      <FilterAccordion
        filterNames={filterNames}
        filterOrder={filterOrder}
        filterString=""
        filtersToString={FilterMachines.filtersToString}
        getCurrentFilters={FilterMachines.getCurrentFilters}
        getValue={getValue}
        isFilterActive={FilterMachines.isFilterActive}
        items={items}
        onUpdateFilterString={() => null}
        toggleFilter={FilterMachines.toggleFilter}
      />
    );

    // Open menu - there shouldn't be an option to filter by link speed
    await userEvent.click(screen.getByRole("button", { name: Labels.Toggle }));
    expect(
      screen.queryByRole("tab", { name: filterNames.get("link_speeds") })
    ).not.toBeInTheDocument();
  });

  it("is disabled if there are no items to display", async () => {
    renderWithProviders(
      <FilterAccordion
        filterNames={filterNames}
        filterOrder={filterOrder}
        filterString=""
        filtersToString={FilterMachines.filtersToString}
        getCurrentFilters={FilterMachines.getCurrentFilters}
        getValue={getValue}
        isFilterActive={FilterMachines.isFilterActive}
        items={[]}
        onUpdateFilterString={() => null}
        toggleFilter={FilterMachines.toggleFilter}
      />
    );

    expect(
      screen.getByRole("button", { name: Labels.Toggle })
    ).toBeAriaDisabled();
  });
});
