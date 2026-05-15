import { Icon, Spinner } from "@canonical/react-components";
import classNames from "classnames";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import {
  useFetchActions,
  useCanEdit,
  useSendAnalytics,
} from "@/app/base/hooks";
import urls from "@/app/base/urls";
import type { ControllerDetails } from "@/app/store/controller/types";
import { generalActions } from "@/app/store/general";
import { PowerTypeNames } from "@/app/store/general/constants";
import { powerTypes as powerTypesSelectors } from "@/app/store/general/selectors";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";
import { getTagsDisplay } from "@/app/store/tag/utils";
import { nodeIsMachine } from "@/app/store/utils";
import { extractPowerType } from "@/app/utils";

type Props = {
  node: ControllerDetails | MachineDetails;
};

export enum Labels {
  Owner = "Owner",
  Host = "Host",
  Zone = "Zone",
  ZoneLink = "Zone ›",
  Pool = "Resource pool",
  PoolLink = "Resource pool ›",
  PowerType = "Power type",
  PowerTypeLink = "Power type ›",
  Tags = "Tags",
  TagsLink = "Tags ›",
  KernelCrashDump = "Kernel crash dump",
}

const DetailsCard = ({ node }: Props): React.ReactElement => {
  const powerTypes = useSelector(powerTypesSelectors.get);
  const tagsLoaded = useSelector(tagSelectors.loaded);
  const machineTags = useSelector((state: RootState) =>
    tagSelectors.getByIDs(state, node.tags)
  );
  const sendAnalytics = useSendAnalytics();
  const canEdit = useCanEdit(node, true);

  const isMachine = nodeIsMachine(node);
  const configTabUrl = isMachine
    ? urls.machines.machine.configuration({ id: node.system_id })
    : urls.controllers.controller.configuration({ id: node.system_id });
  const powerTypeDescription = powerTypes.find(
    (powerType) => powerType.name === node.power_type
  )?.description;
  const powerTypeDisplay = extractPowerType(
    powerTypeDescription || "",
    node.power_type
  );
  const tagsDisplay = getTagsDisplay(machineTags);
  const kernelCrashDumpEnabled = isMachine
    ? node.enable_kernel_crash_dump
    : false;

  useFetchActions([generalActions.fetchPowerTypes, tagActions.fetch]);

  return (
    <div
      className={classNames("overview-card__details", {
        "for-controller": !isMachine,
        "for-machine": isMachine,
      })}
    >
      {isMachine && (
        <div>
          <div className="u-text--muted">{Labels.Owner}</div>
          <span data-testid="owner" title={node.owner || "-"}>
            {node.owner || "-"}
          </span>
        </div>
      )}
      {isMachine && (
        <>
          {node.pod && (
            <div>
              <div className="u-text--muted">{Labels.Host}</div>
              <span data-testid="host">
                <Link
                  className="p-link__chevron"
                  to={
                    node.power_type === PowerTypeNames.LXD
                      ? urls.kvm.lxd.single.index({ id: node.pod.id })
                      : urls.kvm.virsh.details.index({ id: node.pod.id })
                  }
                >
                  {node.pod.name} ›
                </Link>
              </span>
            </div>
          )}
        </>
      )}
      <div data-testid="zone">
        <div>
          {canEdit ? (
            <Link
              className="p-link__chevron"
              onClick={() => {
                sendAnalytics(
                  `${node.node_type_display} details`,
                  "Zone configuration link",
                  `${node.node_type_display} summary tab`
                );
              }}
              to={configTabUrl}
            >
              {Labels.ZoneLink}
            </Link>
          ) : (
            <span className="u-text--muted">{Labels.Zone}</span>
          )}
        </div>
        <span title={node.zone.name}>{node.zone.name}</span>
      </div>
      {isMachine && (
        <div data-testid="resource-pool">
          <div>
            {canEdit ? (
              <Link
                className="p-link__chevron"
                onClick={() => {
                  sendAnalytics(
                    `${node.node_type_display} details`,
                    "Resource pool configuration link",
                    `${node.node_type_display} summary tab`
                  );
                }}
                to={configTabUrl}
              >
                {Labels.PoolLink}
              </Link>
            ) : (
              <span className="u-text--muted">{Labels.Pool}</span>
            )}
          </div>
          <span title={node.pool.name}>{node.pool.name}</span>
        </div>
      )}
      <div>
        <div>
          {canEdit ? (
            <Link
              className="p-link__chevron"
              onClick={() => {
                sendAnalytics(
                  `${node.node_type_display} details`,
                  "Power type configuration link",
                  `${node.node_type_display} summary tab`
                );
              }}
              to={configTabUrl}
            >
              {Labels.PowerTypeLink}
            </Link>
          ) : (
            <span className="u-text--muted">{Labels.PowerType}</span>
          )}
        </div>
        <span data-testid="power-type" title={node.power_type ?? undefined}>
          {powerTypeDisplay || node.power_type || <em>None</em>}
        </span>
      </div>
      <div className="u-break-word">
        <div>
          {canEdit ? (
            <Link
              className="p-link__chevron"
              onClick={() => {
                sendAnalytics(
                  `${node.node_type_display} details`,
                  "Tags configuration link",
                  `${node.node_type_display} summary tab`
                );
              }}
              to={configTabUrl}
            >
              {Labels.TagsLink}
            </Link>
          ) : (
            <span className="u-text--muted">{Labels.Tags}</span>
          )}
        </div>
        {tagsLoaded ? (
          <span data-testid="machine-tags" title={tagsDisplay}>
            {tagsDisplay}
          </span>
        ) : (
          <Spinner data-testid="loading-tags" />
        )}
      </div>
      {isMachine && (
        <div>
          <div className="u-text--muted">{Labels.KernelCrashDump}</div>
          <span>
            {kernelCrashDumpEnabled ? (
              <>
                <Icon name="success-grey" /> enabled
              </>
            ) : (
              <>
                <Icon name="error-grey" /> disabled
              </>
            )}
          </span>
        </div>
      )}
    </div>
  );
};

export default DetailsCard;
