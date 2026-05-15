import { useSelector } from "react-redux";

import NodesTagsLink from "../NodesTagsLink";

import { ControllerMeta } from "@/app/store/controller/types";
import { DeviceMeta } from "@/app/store/device/types";
import { MachineMeta } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag, TagMeta } from "@/app/store/tag/types";

type Props = {
  id: Tag[TagMeta.PK];
};

const AppliedTo = ({ id }: Props): React.ReactElement | null => {
  const tag = useSelector((state: RootState) =>
    tagSelectors.getById(state, id)
  );

  if (!tag) {
    return null;
  }
  const hasMachines = tag.machine_count > 0;
  const hasControllers = tag.controller_count > 0;
  const hasDevices = tag.device_count > 0;
  if (!hasMachines && !hasControllers && !hasDevices) {
    return <>None</>;
  }
  return (
    <>
      {hasMachines ? (
        <NodesTagsLink
          count={tag.machine_count}
          nodeType={MachineMeta.MODEL}
          tags={[tag.name]}
        />
      ) : null}
      {hasControllers ? (
        <NodesTagsLink
          count={tag.controller_count}
          nodeType={ControllerMeta.MODEL}
          tags={[tag.name]}
        />
      ) : null}
      {hasDevices ? (
        <NodesTagsLink
          count={tag.device_count}
          nodeType={DeviceMeta.MODEL}
          tags={[tag.name]}
        />
      ) : null}
    </>
  );
};

export default AppliedTo;
