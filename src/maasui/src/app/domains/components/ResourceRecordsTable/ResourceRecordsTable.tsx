import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";

import type { ResourceRecordsColumnData } from "./useResourceRecordsColumns/useResourceRecordsColumns";
import useResourceRecordsColumns from "./useResourceRecordsColumns/useResourceRecordsColumns";

import usePagination from "@/app/base/hooks/usePagination/usePagination";
import type { Domain, DomainDetails } from "@/app/store/domain/types";

type Props = {
  id: Domain["id"];
  domain: DomainDetails;
};

export enum Labels {
  NoRecords = "Domain contains no records.",
}

const ResourceRecordsTable = ({ id, domain }: Props): ReactElement => {
  const { page, size, handlePageSizeChange, setPage } = usePagination(50);
  const columns = useResourceRecordsColumns({ id });

  const data: ResourceRecordsColumnData[] = domain.rrsets.map((record, i) => ({
    id: i,
    ...record,
  }));

  return (
    <GenericTable
      columns={columns}
      data={data.slice((page - 1) * size, page * size) ?? []}
      isLoading={false}
      noData={Labels.NoRecords}
      pagination={{
        currentPage: page,
        dataContext: "records",
        handlePageSizeChange: handlePageSizeChange,
        isPending: false,
        itemsPerPage: size,
        setCurrentPage: setPage,
        totalItems: domain.rrsets.length ?? 0,
      }}
      sorting={[{ id: "name", desc: false }]}
    />
  );
};

export default ResourceRecordsTable;
