import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import { useFetchActions } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";
import { getVLANDisplay } from "@/app/store/vlan/utils";

type Props = {
  id?: VLAN[VLANMeta.PK] | null;
};

const VLANLink = ({ id }: Props): React.ReactElement => {
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, id)
  );
  const vlansLoading = useSelector(vlanSelectors.loading);
  const vlanDisplay = getVLANDisplay(vlan);

  useFetchActions([vlanActions.fetch]);

  if (vlansLoading) {
    return <Spinner aria-label="Loading VLANs" />;
  }
  if (!vlan) {
    return <>{vlanDisplay}</>;
  }
  return (
    <Link to={urls.networks.vlan.index({ id: vlan.id })}>{vlanDisplay}</Link>
  );
};

export default VLANLink;
