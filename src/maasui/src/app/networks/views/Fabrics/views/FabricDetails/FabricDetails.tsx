import type { ReactElement } from "react";
import { useEffect } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import {
  FabricDetailsHeader,
  FabricSummary,
  FabricVLANsTable,
} from "./components";

import ModelNotFound from "@/app/base/components/ModelNotFound";
import PageContent from "@/app/base/components/PageContent";
import { useGetURLId, useWindowTitle } from "@/app/base/hooks";
import urls from "@/app/networks/urls";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import { FabricMeta } from "@/app/store/fabric/types";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import { isId } from "@/app/utils";

const FabricDetails = (): ReactElement => {
  const dispatch = useDispatch();
  const id = useGetURLId(FabricMeta.PK);
  const fabric = useSelector((state: RootState) =>
    fabricSelectors.getById(state, id)
  );
  const fabricsLoading = useSelector(fabricSelectors.loading);
  const isValidID = isId(id);
  useWindowTitle(`${fabric?.name || "Fabric"} details`);

  useEffect(() => {
    if (isValidID) {
      dispatch(fabricActions.get(id));
      dispatch(fabricActions.setActive(id));
      dispatch(subnetActions.fetch());
    }

    return () => {
      dispatch(fabricActions.setActive(null));
      dispatch(fabricActions.cleanup());
    };
  }, [dispatch, id, isValidID]);

  if (!fabric) {
    const fabricNotFound = !isValidID || !fabricsLoading;

    if (fabricNotFound) {
      return (
        <ModelNotFound
          id={id}
          linkURL={urls.subnets.indexWithParams({ by: "fabric" })}
          modelName="fabric"
        />
      );
    }
  }

  return (
    <PageContent header={<FabricDetailsHeader fabric={fabric} />}>
      {!fabric ? (
        <Spinner text="Loading..." />
      ) : (
        <>
          <FabricSummary fabric={fabric} />
          <FabricVLANsTable fabric={fabric} />
        </>
      )}
    </PageContent>
  );
};

export default FabricDetails;
