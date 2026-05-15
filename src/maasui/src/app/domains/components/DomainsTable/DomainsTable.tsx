import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { useSelector } from "react-redux";

import useDomainsTableColumns from "./useDomainsTableColumns/useDomainsTableColumns";

import usePagination from "@/app/base/hooks/usePagination/usePagination";
import domainSelectors from "@/app/store/domain/selectors";

import "./index.scss";

export const Labels = {
  Domain: "Domain",
  Authoritative: "Authoritative",
  Hosts: "Hosts",
  TotalRecords: "Total records",
  Actions: "Actions",
  AreYouSure:
    "Setting this domain as the default will update all existing machines (in Ready state) with the new default domain. Are you sure?",
  SetDefault: "Set default...",
  ConfirmSetDefault: "Set default",
  TableAction: "Table action",
  ContextualMenu: "Actions",
  TableLable: "Domains table",
  EmptyList: "No domains available.",
  FormTitle: "Set default",
} as const;

const DomainsTable = (): ReactElement => {
  const domains = useSelector(domainSelectors.all);
  const domainsLoading = useSelector(domainSelectors.loading);
  const { page, size, handlePageSizeChange, setPage } = usePagination(50);

  const columns = useDomainsTableColumns();

  return (
    <GenericTable
      aria-label={Labels.TableLable}
      className="domains-table"
      columns={columns}
      data={domains.slice(size * (page - 1), size * page)}
      data-testid="domains-table"
      isLoading={domainsLoading}
      noData={Labels.EmptyList}
      pagination={{
        currentPage: page,
        dataContext: "domains",
        handlePageSizeChange: handlePageSizeChange,
        isPending: false,
        itemsPerPage: size,
        setCurrentPage: setPage,
        totalItems: domains.length,
      }}
      sorting={[
        { id: "is_default", desc: true },
        { id: "name", desc: true },
      ]}
    />
  );
};

export default DomainsTable;
