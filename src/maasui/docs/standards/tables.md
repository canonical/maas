# Table Component Standards

## TL;DR

- Extract column definitions into separate hooks using `useMemo`
- Fetch data using API query hooks (e.g., `usePools`, `useRacks`)
- Use `usePagination` hook for server-side pagination
- Use `TableActions` for simple edit/delete actions, `TableActionsDropdown` for longer action lists
- Always provide `isLoading` and `noData` props
- Disable sorting on action columns
- Write tests in separate `describe` blocks for display, permissions, and actions

## Overview

We use `GenericTable` from `@canonical/maas-react-components` for all modern table implementations. This component is built on top of [TanStack Table](https://tanstack.com/table) and provides a consistent, accessible, and feature-rich table experience.

For full API documentation, see the [GenericTable docs](https://canonical.github.io/maas-react-components/?path=/docs/components-generictable--docs).

## Column Definitions

Column definitions should be extracted into a custom hook in a separate file for maintainability and reusability.

### Example: useMyTableColumns.tsx

```tsx
// Only define custom data types if the API type is not a direct match with table columns
type MyDataType = {
  id: number;
  name: string;
  description: string;
  machine_total_count: number;
  machine_ready_count: number;
};

const useMyTableColumns = (): ColumnDef<MyDataType>[] => {
  return useMemo(
    () => [
      {
        id: "name",
        accessorKey: "name",
        enableSorting: true,
        header: "Name",
        cell: ({ row }) => (
          <Link to={`/items/${row.original.id}`}>{row.original.name}</Link>
        ),
      },
      {
        id: "description",
        accessorKey: "description",
        enableSorting: true,
        header: "Description",
      },
      {
        id: "machines",
        accessorKey: "machine_ready_count",
        enableSorting: true,
        header: "Machines",
        cell: ({ row }) => {
          if (row.original.machine_total_count === 0) {
            return "Empty";
          }
          return `${row.original.machine_ready_count} of ${row.original.machine_total_count} ready`;
        },
      },
    ],
    []
  );
};

export default useMyTableColumns;
```

### Action Columns

For action buttons, disable sorting and use custom rendering. Use `TableActions` for simple edit and delete buttons, or `TableActionsDropdown` for longer lists of actions.

```tsx
import TableActions from "@/app/base/components/TableActions";

{
  id: "actions",
  accessorKey: "id",
  enableSorting: false,
  header: "Actions",
  cell: ({ row }) => {
    return (
      <TableActions
        deleteDisabled={!row.original.permissions.includes("delete")}
        deleteTooltip={
          row.original.machine_total_count > 0
            ? "Cannot delete a pool that contains machines."
            : null
        }
        editDisabled={!row.original.permissions.includes("edit")}
        onDelete={() => handleDelete(row.original.id)}
        onEdit={() => handleEdit(row.original.id)}
      />
    );
  },
}
```

For more complex actions, use `TableActionsDropdown`:

```tsx
{
  id: "actions",
  accessorKey: "id",
  enableSorting: false,
  header: "Actions",
  cell: ({ row }) => {
    return (
      <TableActionsDropdown
        actions={[
          { label: "Edit", onClick: () => handleEdit(row.original.id) },
          { label: "Clone", onClick: () => handleClone(row.original.id) },
          { label: "Delete", onClick: () => handleDelete(row.original.id), disabled: !canDelete },
        ]}
      />
    );
  },
}
```

### Row Click vs Action Columns

- Navigation on row click: use a `<Link>` in the cell renderer of the relevant column (e.g. the name column).
- Edit and delete actions: use `TableActions` or `TableActionsDropdown` in a dedicated actions column.
- Do not mix navigation and action triggers on the same row click — each interaction must have a clear, single target element.

## Table Component Implementation

### Basic Structure

```tsx
const MyTable = () => {
  const columns = useMyTableColumns();
  const { data, isPending } = useMyData();

  return (
    <GenericTable
      columns={columns}
      data={data?.items ?? []}
      isLoading={isPending}
      noData="No items found."
    />
  );
};
```

### With Pagination

Use the `usePagination` hook for server-side pagination. This hook manages page state, page size, and provides debounced values for API calls to reduce unnecessary requests.

```tsx
const MyTable = () => {
  const { page, debouncedPage, size, handlePageSizeChange, setPage } =
    usePagination();

  const { data, isPending } = useMyData({
    page: debouncedPage, // Use debounced value for API calls
    size,
  });

  const columns = useMyTableColumns();

  return (
    <GenericTable
      columns={columns}
      data={data?.items ?? []}
      isLoading={isPending}
      noData="No items found."
      pagination={{
        currentPage: page,
        dataContext: "items", // Used in pagination label (e.g., "1-20 of 50 items")
        handlePageSizeChange: handlePageSizeChange,
        isPending: isPending,
        itemsPerPage: size,
        setCurrentPage: setPage,
        totalItems: data?.total ?? 0,
      }}
      sorting={[{ id: "name", desc: false }]} // Optional: initial sort
      variant="full-height" // Optional: use "full-height" or "regular" (default)
    />
  );
};
```

### With TypeScript Generics

For type safety with complex data structures, use TypeScript generics:

```tsx
type MyRowData = {
  id: number;
  name: string;
  children?: MyRowData[];
};

<GenericTable<MyRowData>
  columns={columns}
  data={rowData}
  getSubRows={(originalRow) => originalRow.children}
  isLoading={loading}
  noData="No items found."
/>;
```

## Testing Standards

Every table component should have comprehensive tests organized into separate `describe` blocks for different concerns.

### Test Structure

```tsx
describe("MyTable", () => {
  describe("display", () => {
    // Display-related tests
  });

  describe("permissions", () => {
    // Permission-related tests
  });

  describe("actions", () => {
    // Action/interaction tests
  });
});
```

### Display Tests

Test loading states, empty states, column headers, and data rendering:

```tsx
describe("display", () => {
  it("displays a loading component when data is loading", async () => {
    mockIsPending();
    renderWithProviders(<MyTable />);

    await waitFor(() => {
      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });
  });

  it("displays a message when rendering an empty list", async () => {
    mockServer.use(myResolver.handler({ items: [], total: 0 }));
    renderWithProviders(<MyTable />);

    await waitFor(() => {
      expect(screen.getByText("No items found.")).toBeInTheDocument();
    });
  });

  it("displays the columns correctly", () => {
    renderWithProviders(<MyTable />);

    ["Name", "Status", "Actions"].forEach((column) => {
      expect(
        screen.getByRole("columnheader", {
          name: new RegExp(`^${column}`, "i"),
        })
      ).toBeInTheDocument();
    });
  });

  it("displays data correctly", async () => {
    mockServer.use(
      myResolver.handler({
        items: [{ id: 1, name: "Test Item", status: "active" }],
        total: 1,
      })
    );

    renderWithProviders(<MyTable />);

    await waitFor(() => {
      const row = screen.getByRole("row", {
        name: /Test Item/i,
      });
      expect(within(row).getByText("active")).toBeInTheDocument();
    });
  });
});
```

### Permission Tests

Test permission-based UI states:

```tsx
describe("permissions", () => {
  it("enables action buttons with correct permissions", async () => {
    mockServer.use(
      myResolver.handler({
        items: [factory.item({ permissions: ["edit", "delete"] })],
        total: 1,
      })
    );

    renderWithProviders(<MyTable />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Edit" })
      ).not.toBeAriaDisabled();
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Delete" })
      ).not.toBeAriaDisabled();
    });
  });

  it("disables action buttons without permissions", async () => {
    mockServer.use(
      myResolver.handler({
        items: [factory.item({ permissions: [] })],
        total: 1,
      })
    );

    renderWithProviders(<MyTable />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Edit" })).toBeAriaDisabled();
    });
  });
});
```

### Action Tests

Test user interactions and side effects:

```tsx
import { mockSidePanel, renderWithProviders, screen, userEvent, waitFor } from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("actions", () => {
  it("can trigger edit action", async () => {
    renderWithProviders(<MyTable />);

    await waitFor(() => {
      const editButton = screen.getByRole("button", { name: /edit/i });
      expect(editButton).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: /edit/i }));

    expect(mockOpen).toHaveBeenCalledWith({
      component: EditForm,
      title: "Edit item",
      props: {
        itemId: 1,
      },
    });
  });

  it("handles pagination correctly", async () => {
    mockServer.use(myResolver.handler({ items: mockItems, total: 50 }));

    renderWithProviders(<MyTable />);

    await waitFor(() => {
      expect(screen.getByText(/1-20 of 50/)).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: /next page/i }));

    await waitFor(() => {
      expect(screen.getByText(/21-40 of 50/)).toBeInTheDocument();
    });
  });
});
```
