import { useMemo } from "react";

import { ContextualMenu } from "@canonical/react-components";
import type { ColumnDef } from "@tanstack/react-table";
import { useDispatch } from "react-redux";
import { Link } from "react-router";

import { Labels } from "../DomainsTable";

import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import { SetDefaultForm } from "@/app/domains/components";
import { domainActions } from "@/app/store/domain";
import type { Domain } from "@/app/store/domain/types";

export type DomainsColumnDef = ColumnDef<Domain, Partial<Domain>>;

const useDomainsTableColumns = (): DomainsColumnDef[] => {
  const dispatch = useDispatch();
  const { openSidePanel } = useSidePanel();

  return useMemo(
    (): DomainsColumnDef[] => [
      {
        id: "name",
        accessorKey: "name",
        header: "Domain",
        cell: ({ row: { original: domain } }) => (
          <Link
            aria-label={domain.name}
            data-testid="domain-name"
            to={urls.domains.details({ id: domain.id })}
          >
            {domain.is_default ? `${domain.name} (default)` : domain.name}
          </Link>
        ),
      },
      {
        id: "authoritative",
        accessorKey: "authoritative",
        header: "Authoritative",
        cell: ({ row: { original: domain } }) => (
          <span aria-label={Labels.Authoritative}>
            {domain.authoritative ? "Yes" : "No"}
          </span>
        ),
      },
      {
        id: "hosts",
        accessorKey: "hosts",
        header: "Hosts",
        cell: ({ row: { original: domain } }) => (
          <span aria-label={Labels.Hosts}>{domain.hosts}</span>
        ),
      },
      {
        id: "resource_count",
        accessorKey: "resource_count",
        header: "Total records",
        cell: ({ row: { original: domain } }) => (
          <span aria-label={Labels.TotalRecords}>{domain.resource_count}</span>
        ),
      },
      {
        id: "actions",
        header: "Actions",
        enableSorting: false,
        cell: ({ row: { original: domain } }) => (
          <ContextualMenu
            aria-label={Labels.Actions}
            hasToggleIcon={true}
            links={[
              {
                children: Labels.SetDefault,
                onClick: () => {
                  dispatch(domainActions.cleanup());
                  openSidePanel({
                    component: SetDefaultForm,
                    title: "Set default",
                    props: { id: domain.id },
                  });
                },
              },
            ]}
            toggleAppearance="base"
            toggleClassName="u-no-margin--bottom is-small is-dense"
            toggleDisabled={domain.is_default}
          />
        ),
      },
    ],
    [dispatch, openSidePanel]
  );
};

export default useDomainsTableColumns;
