import pluralize from "pluralize";
import { Link, useLocation } from "react-router";

import urls from "@/app/base/urls";
import { ControllerMeta } from "@/app/store/controller/types";
import { DeviceMeta } from "@/app/store/device/types";
import { MachineMeta } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import type { Tag } from "@/app/store/tag/types";
import type { NodeModel } from "@/app/store/types/node";

type Props = {
  count: number;
  nodeType: NodeModel;
  tags: Tag["name"][];
};

const NodesTagsLink = ({
  count,
  nodeType,
  tags,
}: Props): React.ReactElement | null => {
  const { pathname } = useLocation();

  let url: string | null = null;
  let nodeName: string | null = null;
  switch (nodeType) {
    case MachineMeta.MODEL:
      url = urls.machines.index;
      nodeName = "machine";
      break;
    case ControllerMeta.MODEL:
      url = urls.controllers.index;
      nodeName = "controller";
      break;
    case DeviceMeta.MODEL:
      url = urls.devices.index;
      nodeName = "device";
      break;
  }
  if (!url || !nodeName) {
    return null;
  }

  const filters = FilterMachines.filtersToQueryString({
    tags: [`=${tags.join(",")}`],
  });

  return (
    <Link
      className="u-display--block"
      reloadDocument={
        // reload the document if it's a machine list link clicked from machine listing page
        // this is a hack to get around the fact that the machine listing page doesn't update when the URL changes
        // TODO: remove the workaround below once https://github.com/canonical/maas-ui/issues/4603 is fixed
        pathname.startsWith(url) && pathname.startsWith(urls.machines.index)
      }
      to={`${url}${filters}`}
    >
      {pluralize(nodeName, count, true)}
    </Link>
  );
};

export default NodesTagsLink;
