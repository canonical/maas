# Constants

## TL;DR

- Three levels: app-level (`src/app/constants.ts`), domain-level (`<domain>/constants.ts`), view-level (inline or subfolder).
- Only add to `src/app/constants.ts` when a value is used across 2+ unrelated domains.
- Co-locate domain constants in `src/app/<domain>/constants.ts`.
- Use `as const` arrays to derive union types; prefer this over loose `string` types for column/key lists.
- Use TypeScript enums for sets of related string values referenced across multiple components.
- Use `Record<Enum, string>` for label maps — one source of truth per label.
- Navigation structure (secondary nav items) lives in the domain's `constants.ts`, not inline in components.
- Never scatter magic strings (column names, status values, label text) across component files.
- Never put domain-specific constants in `src/app/constants.ts`.
- Constants have no runtime behaviour — they do not need dedicated test files; test them indirectly through the components that use them.

---

## App-Level Constants

`src/app/constants.ts` holds values that are consumed by 2+ unrelated domains.

```ts
export const MAAS_UI_ID = "maas-ui";
export const MOBILE_VIEW_MAX_WIDTH = 620;
```

The bar for adding here is high. If a value is only used within one domain, it belongs in that domain's `constants.ts`.

### Do

```ts
// src/app/constants.ts
export const MAAS_UI_ID = "maas-ui";
```

### Don't

```ts
// src/app/constants.ts — wrong: machines-specific value does not belong here
export const MACHINE_LIST_PAGE_SIZE = 50;
```

---

## Domain-Level Constants

Each domain that has reusable constant values owns a `src/app/<domain>/constants.ts` file. This is the right place for column definitions, enum types, label maps, group options, and navigation structure.

### Column Arrays, Derived Types, and Enums

The pattern from `src/app/machines/constants.ts`:

```ts
export const columns = [
  "fqdn",
  "power",
  "status",
  "owner",
  "pool",
  "zone",
  "fabric",
  "cpu",
  "memory",
  "disks",
  "storage",
] as const;
export type MachineColumn = (typeof columns)[number];
export type MachineColumnToggle = Exclude<MachineColumn, "fqdn">;

export enum MachineColumns {
  FQDN = "fqdn",
  POWER = "power",
  STATUS = "status",
  OWNER = "owner",
  POOL = "pool",
  ZONE = "zone",
  FABRIC = "fabric",
  CPU = "cpu",
  MEMORY = "memory",
  DISKS = "disks",
  STORAGE = "storage",
}

export const columnLabels: Record<MachineColumns, string> = {
  fqdn: "FQDN",
  power: "Power",
  status: "Status",
  owner: "Owner",
  pool: "Pool",
  zone: "Zone",
  fabric: "Fabric",
  cpu: "Cores",
  memory: "RAM",
  disks: "Disks",
  storage: "Storage",
};
```

The pattern in full:

1. `as const` array — the authoritative list, iterable at runtime.
2. Derived union type (`MachineColumn`) — enforces valid values at compile time.
3. Enum (`MachineColumns`) — named references for use in component props and switch statements.
4. `Record<Enum, string>` label map (`columnLabels`) — single source of truth for human-readable labels.

Adding a new column means updating all four in one place. The compiler will surface every component that needs updating via the `Record` exhaustiveness check.

### Do

```ts
import { MachineColumns, columnLabels } from "@/app/machines/constants";

<TableHeader>{columnLabels[MachineColumns.CPU]}</TableHeader>
```

### Don't

```ts
<TableHeader>{"Cores"}</TableHeader>
```

---

### Group / Select Options

Option arrays for dropdowns belong in the domain's `constants.ts`, typed against their value union.

From `src/app/machines/constants.ts`:

```ts
export const groupOptions: { value: FetchGroupKey | ""; label: string }[] = [
  { value: "", label: "No grouping" },
  { value: FetchGroupKey.Status, label: "Group by status" },
  { value: FetchGroupKey.Owner, label: "Group by owner" },
  { value: FetchGroupKey.Pool, label: "Group by resource pool" },
  { value: FetchGroupKey.Architecture, label: "Group by architecture" },
  { value: FetchGroupKey.Domain, label: "Group by domain" },
  { value: FetchGroupKey.Parent, label: "Group by parent" },
  { value: FetchGroupKey.Pod, label: "Group by KVM" },
  { value: FetchGroupKey.PodType, label: "Group by KVM type" },
  { value: FetchGroupKey.PowerState, label: "Group by power state" },
  { value: FetchGroupKey.Zone, label: "Group by zone" },
];
```

### Do

```ts
import { groupOptions } from "@/app/machines/constants";

<Select options={groupOptions} />
```

### Don't

```ts
<Select
  options={[
    { value: "", label: "No grouping" },
    { value: "status", label: "Group by status" },
  ]}
/>
```

---

## Navigation Constants

Secondary navigation structure lives in `constants.ts` at the domain root, typed as `NavItem[]`. This keeps the nav definition separate from the component that renders it.

From `src/app/settings/constants.ts`:

```ts
import type { NavItem } from "@/app/base/components/SecondaryNavigation/SecondaryNavigation";
import settingsURLs from "@/app/settings/urls";

export const settingsNavItems: NavItem[] = [
  {
    label: "Configuration",
    items: [
      { path: settingsURLs.configuration.general, label: "General" },
      { path: settingsURLs.configuration.commissioning, label: "Commissioning" },
      { path: settingsURLs.configuration.deploy, label: "Deploy" },
      { path: settingsURLs.configuration.kernelParameters, label: "Kernel parameters" },
    ],
  },
  {
    label: "Security",
    items: [
      { path: settingsURLs.security.securityProtocols, label: "Security protocols" },
      { path: settingsURLs.security.secretStorage, label: "Secret storage" },
      { path: settingsURLs.security.sessionTimeout, label: "Token expiration" },
      { path: settingsURLs.security.ipmiSettings, label: "IPMI settings" },
    ],
  },
];
```

Path values come from the domain's `urls.ts` — never hard-code path strings here.

### Do

```ts
import { settingsNavItems } from "@/app/settings/constants";

<SecondaryNavigation items={settingsNavItems} />
```

### Don't

```ts
<SecondaryNavigation
  items={[{ label: "Configuration", items: [{ path: "/settings/general", label: "General" }] }]}
/>
```

---

## View-Level Constants

Small, single-use values (a local page size, a one-off timeout) that are only relevant to a single view can be defined inline in that view file or in a sibling constants file within the view folder. Do not promote them to the domain's `constants.ts` unless a second consumer appears.

---

## Dos and Don'ts

| | Do | Don't |
|---|---|---|
| Scope | Co-locate domain constants in `<domain>/constants.ts`. | Put domain-specific constants in `src/app/constants.ts`. |
| Typing | Use `as const` arrays and derive union types from them. | Use bare `string` types for values that form a fixed set. |
| Enums | Use enums for sets of related string values used across components. | Reference column names or status values as raw string literals in components. |
| Labels | Use `Record<Enum, string>` for label maps. | Duplicate label text across multiple components. |
| Nav | Define secondary nav item arrays in `constants.ts` using `urls.ts` paths. | Hard-code path strings in nav item arrays. |
| Options | Define dropdown option arrays in `constants.ts` typed against their value union. | Inline option arrays inside component JSX. |
