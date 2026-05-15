import { Notification as NotificationBanner } from "@canonical/react-components";
import pluralize from "pluralize";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import urls from "@/app/base/urls";
import { FilterMachines } from "@/app/store/machine/utils";
import { useFetchMachineCount } from "@/app/store/machine/utils/hooks";
import type { RootState } from "@/app/store/root/types";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag, TagMeta } from "@/app/store/tag/types";
import { FetchNodeStatus } from "@/app/store/types/node";

type Props = {
  id: Tag[TagMeta.PK];
};

const generateWarning = (nodeType: string, count: number) => (
  <NotificationBanner
    className="delete-tag-form-warnings__notification"
    severity="caution"
  >
    There {count === 1 ? "is" : "are"} {pluralize(nodeType, count, true)} with
    this tag.
  </NotificationBanner>
);

const generateDeployedMessage = (count: number) =>
  count === 1
    ? `There is ${count} deployed machine with this tag and it will not be affected until it is redeployed.`
    : `There are ${count} deployed machines with this tag and they will not be affected until they are redeployed.`;

export const DeleteTagFormWarnings = ({
  id,
}: Props): React.ReactElement | null => {
  const tag = useSelector((state: RootState) =>
    tagSelectors.getById(state, id)
  );
  const { machineCount: deployedCount } = useFetchMachineCount({
    status: [FetchNodeStatus.DEPLOYED],
    ...(tag?.id ? { tags: [tag.name] } : {}),
  });
  if (!tag) {
    return null;
  }
  return (
    <div className="delete-tag-form-warnings">
      {!!tag.kernel_opts && deployedCount > 0 ? (
        <NotificationBanner
          className="delete-tag-form-warnings__notification"
          severity="caution"
        >
          <span className="u-display--block">
            You are deleting a tag with kernel options.{" "}
            {generateDeployedMessage(deployedCount)}
          </span>
          <Link
            to={`${urls.machines.index}${FilterMachines.filtersToQueryString({ tags: [`=${tag.name}`] })}`}
          >
            Show the deployed {pluralize("machine", deployedCount)}
          </Link>
        </NotificationBanner>
      ) : null}
      {tag.device_count > 0
        ? generateWarning("device", tag.device_count)
        : null}
      {tag.controller_count > 0
        ? generateWarning("controller", tag.controller_count)
        : null}
    </div>
  );
};

export default DeleteTagFormWarnings;
