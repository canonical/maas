import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";

import useEventLogsTableColumns from "@/app/base/components/node/NodeLogs/EventLogs/EventLogsTable/useEventLogsTableColumns/useEventLogsTableColumns";
import type { EventRecord } from "@/app/store/event/types";

import "./index.scss";

type EventLogsTableProps = {
  events: EventRecord[];
  loading: boolean;
};

const EventLogsTable = ({
  events,
  loading,
}: EventLogsTableProps): ReactElement => {
  const columns = useEventLogsTableColumns();

  return (
    <GenericTable
      aria-label="Event logs table"
      className="event-logs-table"
      columns={columns}
      data={events}
      isLoading={loading}
      noData="No event logs available."
      variant="regular"
    />
  );
};

export default EventLogsTable;
