import { useMemo } from "react";

import { ExternalLink } from "@canonical/maas-react-components";
import type { ColumnDef } from "@tanstack/react-table";

import StatusColumn from "../../StatusColumn";
import VLANsColumn from "../../VLANsColumn";
import VersionColumn from "../../VersionColumn";

import ControllerLink from "@/app/base/components/ControllerLink";
import DoubleRow from "@/app/base/components/DoubleRow";
import TooltipButton from "@/app/base/components/TooltipButton";
import docsUrls from "@/app/base/docsUrls";
import type { Controller } from "@/app/store/controller/types";
import { NodeType } from "@/app/store/types/node";

type ControllerColumnDef = ColumnDef<Controller, Partial<Controller>>;

type Props = {
  vaultEnabled: boolean;
  configuredControllers: number;
};

const useControllersTableColumns = ({
  vaultEnabled,
  configuredControllers,
}: Props): ControllerColumnDef[] => {
  return useMemo(
    () => [
      {
        id: "fqdn",
        header: "Name",
        accessorKey: "fqdn",
        enableSorting: true,
        cell: ({ row }) => <ControllerLink systemId={row.original.system_id} />,
      },
      {
        id: "status",
        header: "Status",
        accessorKey: "status",
        enableSorting: false,
        cell: ({ row }) => <StatusColumn controller={row.original} />,
      },
      {
        id: "node_type",
        header: "Type",
        accessorKey: "node_type",
        enableSorting: true,
        cell: ({ row: { original: controller } }) => (
          <span className="u-truncate">
            {controller.node_type === NodeType.REGION_CONTROLLER ||
            controller.node_type === NodeType.REGION_AND_RACK_CONTROLLER ? (
              vaultEnabled ? (
                <TooltipButton
                  aria-label="security"
                  iconName="security-tick"
                  iconProps={{
                    "data-testid": "vault-icon",
                    "aria-describedby": "tooltip-description-tick",
                  }}
                  message={
                    <p id="tooltip-description-tick">
                      Vault is configured on this region controller for secret
                      storage.
                      <br />
                      <ExternalLink
                        className="is-on-dark"
                        to={docsUrls.vaultIntegration}
                      >
                        Read more about Vault integration
                      </ExternalLink>
                    </p>
                  }
                />
              ) : controller.vault_configured === true ? (
                <TooltipButton
                  aria-label="security"
                  iconName="security"
                  iconProps={{
                    "data-testid": "vault-icon",
                    "aria-describedby": "tooltip-description",
                  }}
                  message={
                    <p id="tooltip-description">
                      Vault is configured on this controller. <br />
                      Once all controllers are configured, migrate the secrets.{" "}
                      <br />
                      <ExternalLink
                        className="is-on-dark"
                        to={docsUrls.vaultIntegration}
                      >
                        Read more about Vault integration
                      </ExternalLink>
                    </p>
                  }
                />
              ) : (
                configuredControllers >= 1 && (
                  <TooltipButton
                    aria-label="security"
                    iconName="security-warning"
                    iconProps={{
                      "data-testid": "vault-icon",
                      "aria-describedby": "tooltip-description-warning",
                    }}
                    message={
                      <p id="tooltip-description-warning">
                        Missing Vault configuration.
                        <br />
                        <ExternalLink
                          className="is-on-dark"
                          to={docsUrls.vaultIntegration}
                        >
                          Read more about Vault integration
                        </ExternalLink>
                      </p>
                    }
                  />
                )
              )
            ) : null}
            {` ${controller.node_type_display}`}
          </span>
        ),
      },
      {
        id: "vlans",
        header: "# of VLANs",
        accessorKey: "vlans_ha",
        enableSorting: false,
        cell: ({ row }) => <VLANsColumn controller={row.original} />,
      },
      {
        id: "versions",
        header: () => (
          <DoubleRow
            primary="Version"
            primaryTitle="Version"
            secondary="Channel"
            secondaryTitle="Channel"
          />
        ),
        accessorKey: "versions",
        accessorFn: (controller) => {
          return controller.versions?.current.version;
        },
        enableSorting: true,
        cell: ({ row }) => <VersionColumn controller={row.original} />,
      },
      {
        id: "upgrades",
        header: "Available Upgrades",
        accessorKey: "upgrades_available",
        enableSorting: false,
        cell: ({ row }) => (
          <>
            {row.original.versions?.up_to_date
              ? "Up-to-date"
              : row.original.versions?.update?.version || null}
          </>
        ),
      },
    ],
    [configuredControllers, vaultEnabled]
  );
};

export default useControllersTableColumns;
