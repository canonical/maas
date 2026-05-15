import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import { useFetchActions } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { Fabric, FabricMeta } from "@/app/store/fabric/types";
import { getFabricDisplay } from "@/app/store/fabric/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  id?: Fabric[FabricMeta.PK] | null;
};

export enum Labels {
  Loading = "Loading fabrics",
}

const FabricLink = ({ id }: Props): React.ReactElement => {
  const fabric = useSelector((state: RootState) =>
    fabricSelectors.getById(state, id)
  );
  const fabricsLoading = useSelector(fabricSelectors.loading);
  const fabricDisplay = getFabricDisplay(fabric);

  useFetchActions([fabricActions.fetch]);

  if (fabricsLoading) {
    return <Spinner aria-label={Labels.Loading} />;
  }
  if (!fabric) {
    return <>{fabricDisplay}</>;
  }
  return (
    <Link to={urls.networks.fabric.index({ id: fabric.id })}>
      {fabricDisplay}
    </Link>
  );
};

export default FabricLink;
