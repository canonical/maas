import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import { useFetchActions } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import { getSubnetDisplay } from "@/app/store/subnet/utils";

type Props = {
  id?: Subnet[SubnetMeta.PK] | null;
};

const SubnetLink = ({ id }: Props): React.ReactElement => {
  const subnet = useSelector((state: RootState) =>
    subnetSelectors.getById(state, id)
  );
  const subnetsLoading = useSelector(subnetSelectors.loading);
  const subnetDisplay = getSubnetDisplay(subnet);

  useFetchActions([subnetActions.fetch]);

  if (subnetsLoading) {
    return <Spinner aria-label="Loading subnets" />;
  }
  if (!subnet) {
    return <>{subnetDisplay}</>;
  }
  return (
    <Link to={urls.networks.subnet.index({ id: subnet.id })}>
      {subnetDisplay}
    </Link>
  );
};

export default SubnetLink;
