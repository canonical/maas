import { useMemo } from "react";

import { Icon } from "@canonical/react-components";
import type { ColumnDef, Row } from "@tanstack/react-table";

import type { EventRecord } from "@/app/store/event/types";

type EventLogColumnDef = ColumnDef<EventRecord, Partial<EventRecord>>;

const useEventLogsTableColumns = (): EventLogColumnDef[] => {
  return useMemo(
    () => [
      {
        id: "time",
        accessorKey: "created",
        header: "Time",
        cell: ({
          row: {
            original: { type, created },
          },
        }: {
          row: Row<EventRecord>;
        }) => {
          let icon: string = type.level;
          switch (icon) {
            case "audit":
            case "info":
              icon = "information";
              break;
            case "critical":
              icon = "error";
              break;
            case "debug":
              icon = "inspector-debug";
              break;
          }
          return (
            <>
              <Icon name={icon} /> {created}
            </>
          );
        },
      },
      {
        id: "event",
        accessorKey: "description",
        header: "Event",
        cell: ({
          row: {
            original: { type, description },
          },
        }: {
          row: Row<EventRecord>;
        }) => [type.description, description].filter(Boolean).join(" - "),
      },
    ],
    []
  );
};

export default useEventLogsTableColumns;
