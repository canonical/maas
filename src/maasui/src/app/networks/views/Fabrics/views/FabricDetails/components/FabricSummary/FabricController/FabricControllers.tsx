import { useEffect } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import ControllerLink from "@/app/base/components/ControllerLink";
import Definition from "@/app/base/components/Definition";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Fabric, FabricMeta } from "@/app/store/fabric/types";
import type { RootState } from "@/app/store/root/types";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";

type Props = {
  id: Fabric[FabricMeta.PK];
};

const FabricControllers = ({ id }: Props): React.ReactElement => {
  const controllers = useSelector((state: RootState) =>
    controllerSelectors.getByFabricId(state, id)
  );
  const controllersLoaded = useSelector(controllerSelectors.loaded);
  const dispatch = useDispatch();

  const vlansLoaded = useSelector(vlanSelectors.loaded);

  useEffect(() => {
    if (!vlansLoaded) dispatch(vlanActions.fetch());
    if (!controllersLoaded) dispatch(controllerActions.fetch());
  }, [dispatch, vlansLoaded, controllersLoaded]);

  return (
    <Definition label="Rack controllers">
      {!controllersLoaded || !vlansLoaded ? (
        <span data-testid="Spinner">
          <Spinner />
        </span>
      ) : (
        controllers.map((controller) =>
          controller ? (
            <ControllerLink
              key={controller.id}
              systemId={controller.system_id}
            />
          ) : null
        )
      )}
    </Definition>
  );
};

export default FabricControllers;
