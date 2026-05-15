import type { ReactNode } from "react";

import { Spinner } from "@canonical/react-components";

import type { TableStatus } from "./getTableStatus";

export const generateEmptyStateMsg = (
  status: TableStatus,
  customLabelMapping: Partial<Record<TableStatus, ReactNode>> = {}
): ReactNode => {
  const defaultLabelMapping = {
    loading: <Spinner text="Loading..." />,
    filtered: "No data matches the search criteria.",
    default: "No data is available.",
  };

  const labelMapping = {
    ...defaultLabelMapping,
    ...customLabelMapping,
  };

  return labelMapping[status];
};
