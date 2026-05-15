import classNames from "classnames";
import { useSelector } from "react-redux";

import DHCPTable from "@/app/base/components/DHCPTable";
import { useFetchActions } from "@/app/base/hooks";
import { ipRangeActions } from "@/app/store/iprange";
import ipRangeSelectors from "@/app/store/iprange/selectors";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";

type Props = {
  modelName: string;
  subnetIds: Subnet[SubnetMeta.PK][];
};

const DHCPSnippets = ({ modelName, subnetIds }: Props): React.ReactElement => {
  const subnets = useSelector((state: RootState) =>
    subnetSelectors.getByIds(state, subnetIds)
  );
  const ipranges = useSelector(ipRangeSelectors.all);

  useFetchActions([subnetActions.fetch, ipRangeActions.fetch]);

  return (
    <DHCPTable
      className={classNames({ "u-no-padding--top": modelName === "subnet" })}
      ipRanges={ipranges}
      modelName={modelName}
      subnets={subnets}
    />
  );
};

export default DHCPSnippets;
