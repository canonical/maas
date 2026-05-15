import type { FetchFilters } from "../types/actions";

import { FilterMachines } from "./search";

const scenarios: {
  filters: FetchFilters;
  input: string;
  output?: string;
}[] = [
  { input: "system_id:abc123", filters: { id: ["abc123"] } },
  {
    input: "cores:1",
    filters: {
      cpu_count: [1],
    },
  },
  {
    input: "cpu:1",
    filters: {
      cpu_count: [1],
    },
  },
  {
    input: "cpu:1 cores:2",
    filters: {
      cpu_count: [1, 2],
    },
  },
  {
    input: "mac:aa:bb:cc:dd",
    filters: {
      mac_address: ["aa:bb:cc:dd"],
    },
  },
  {
    input: "ram:1",
    filters: {
      mem: [1],
    },
  },
  {
    input: "release:ubuntu/jammy",
    filters: {
      osystem: ["ubuntu"],
      distro_series: ["jammy"],
    },
  },
  {
    input: "vlan:vlan1",
    filters: {
      vlans: ["vlan1"],
    },
  },
  {
    input: "vlan:vlan1,!vlan2",
    filters: {
      vlans: ["vlan1"],
      not_vlans: ["vlan2"],
    },
  },
  {
    input: "workload-type:()",
    filters: {
      workloads: ["type:"],
    },
  },
  {
    input: "workload-type:(qwerty)",
    filters: {
      workloads: ["type:qwerty"],
    },
  },
  {
    input: "free-text workload-type:(qwerty) workload-service:(dvorak)",
    filters: {
      free_text: ["free-text"],
      workloads: ["type:qwerty", "service:dvorak"],
    },
  },
  {
    input: "workload-type:(query with spaces)",
    filters: {
      workloads: ["type:query with spaces"],
    },
  },
];

describe("parseFetchFilters", () => {
  scenarios.forEach((scenario) => {
    it(`can parse: ${scenario.input}`, () => {
      expect(FilterMachines.parseFetchFilters(scenario.input)).toEqual(
        scenario.filters
      );
    });
  });
});

it("workload annotation is active if key exists in filter list", () => {
  expect(
    FilterMachines.isFilterActive(
      {
        "workload-type": ["type:production"],
      },
      "workloads",
      "type"
    )
  ).toBe(true);
});

it("isNonEmptyFilter returns false for empty search string", () => {
  expect(FilterMachines.isNonEmptyFilter("")).toBe(false);
});

it("isNonEmptyFilter returns true for defined search string", () => {
  expect(FilterMachines.isNonEmptyFilter("status:(=broken)")).toBe(true);
});
