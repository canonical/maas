import { ExternalLink } from "@canonical/maas-react-components";
import { Tooltip } from "@canonical/react-components";
import { formatDuration, intervalToDuration } from "date-fns";
import { useSelector } from "react-redux";

import TooltipButton from "@/app/base/components/TooltipButton";
import docsUrls from "@/app/base/docsUrls";
import type { Seconds } from "@/app/base/types";
import { PowerTypeNames } from "@/app/store/general/constants";
import type { MachineDetails } from "@/app/store/machine/types";
import { useFormattedOS } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag } from "@/app/store/tag/types";
import {
  NodeStatus,
  NodeStatusCode,
  TestStatusStatus,
} from "@/app/store/types/node";
import { breakLines, isEphemerallyDeployed } from "@/app/utils";

type Props = {
  machine: MachineDetails;
};

const isVM = (machine: MachineDetails, machineTags: Tag[]) => {
  if (machineTags.some((tag) => tag.name === "virtual")) {
    return true;
  }
  const vmPowerTypes = [
    PowerTypeNames.LXD,
    PowerTypeNames.VIRSH,
    PowerTypeNames.VMWARE,
  ];
  return vmPowerTypes.some((type) => type === machine.power_type);
};

const showFailedTestsWarning = (machine: MachineDetails) => {
  switch (machine.status_code) {
    case NodeStatusCode.COMMISSIONING:
    case NodeStatusCode.TESTING:
      return false;
  }

  return machine.testing_status === TestStatusStatus.FAILED;
};

const formatSyncInterval = (syncInterval: Seconds) =>
  formatDuration(
    intervalToDuration({
      start: 0,
      end: syncInterval * 1000,
    })
  );

const MachineStatusCard = ({ machine }: Props): React.ReactElement => {
  const formattedOS = useFormattedOS(machine);
  const machineTags = useSelector((state: RootState) =>
    tagSelectors.getByIDs(state, machine.tags)
  );

  return (
    <>
      <div className="overview-card__status" data-testid="machine-status">
        <strong className="p-muted-heading u-flex--between u-no-margin--bottom u-no-padding--top">
          {isVM(machine, machineTags)
            ? "Virtual Machine Status"
            : "Machine Status"}
        </strong>

        <h4 className="u-no-margin--bottom">
          {machine.locked && (
            <i className="p-icon--locked is-inline" data-testid="locked">
              Locked
            </i>
          )}
          {machine.status}
          {isEphemerallyDeployed(machine) && (
            <span className="p-text--small"> in memory</span>
          )}
        </h4>

        {machine.show_os_info ? (
          <p className="u-text--muted" data-testid="os-info">
            {formattedOS}
          </p>
        ) : null}
        {machine.error_description &&
        machine.status_code === NodeStatusCode.BROKEN ? (
          <p
            className="u-text--muted u-truncate"
            data-testid="error-description"
          >
            <Tooltip
              message={breakLines(machine.error_description)}
              position="btm-left"
              positionElementClassName="p-double-row__tooltip-inner"
              tooltipClassName="p-tooltip--fixed-width"
            >
              {machine.error_description}
            </Tooltip>
          </p>
        ) : null}
        {machine.status === NodeStatus.DEPLOYED && machine.enable_hw_sync ? (
          <>
            <hr />
            <p className="u-text--muted">
              Periodic hardware sync enabled{" "}
              <TooltipButton
                aria-label="more about periodic hardware sync"
                className="u-nudge-right--small"
                iconName="help"
                message={
                  <>
                    This machine hardware info is synced every{" "}
                    {formatSyncInterval(machine.sync_interval)}.{"\n"}
                    You can check it at the bottom, in the status bar.{"\n"}
                    More about this in the{" "}
                    <ExternalLink
                      className="is-on-dark"
                      to={docsUrls.hardwareSync}
                    >
                      Hardware sync docs
                    </ExternalLink>
                    .
                  </>
                }
                position="right"
              />
            </p>
          </>
        ) : null}
      </div>
      {showFailedTestsWarning(machine) ? (
        <div
          className="overview-card__test-warning u-flex--vertically"
          data-testid="failed-test-warning"
        >
          <ul className="overview-card__test-text p-inline-list u-no-margin--bottom">
            <li className="p-inline-list__item">
              <span>
                <i className="p-icon--warning">Warning:</i> Some tests failed,
                use with caution.
              </span>
            </li>
          </ul>
        </div>
      ) : null}
    </>
  );
};

export default MachineStatusCard;
