import { useEffect } from "react";

import { useDispatch } from "react-redux";
import { Outlet, useLocation } from "react-router";

import MachineHeader from "./MachineHeader";

import ModelNotFound from "@/app/base/components/ModelNotFound";
import PageContent from "@/app/base/components/PageContent";
import { useGetURLId } from "@/app/base/hooks/urls";
import urls from "@/app/base/urls";
import { machineActions } from "@/app/store/machine";
import { MachineMeta } from "@/app/store/machine/types";
import { useFetchMachine } from "@/app/store/machine/utils/hooks";
import { tagActions } from "@/app/store/tag";
import { isId } from "@/app/utils";

const MachineDetails = (): React.ReactElement => {
  const dispatch = useDispatch();
  const id = useGetURLId(MachineMeta.PK);
  const { pathname } = useLocation();
  const { machine, loaded: detailsLoaded, error } = useFetchMachine(id);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  useEffect(() => {
    if (isId(id)) {
      // Set machine as active to ensure all machine data is sent from the server.
      dispatch(machineActions.setActive(id));
      dispatch(tagActions.fetch());
    }
    // Unset active machine on cleanup.
    return () => {
      dispatch(machineActions.setActive(null));
      // Clean up any machine errors etc. when closing the details.
      dispatch(machineActions.cleanup());
    };
  }, [dispatch, id]);

  if (!isId(id) || (detailsLoaded && !machine) || error) {
    return (
      <ModelNotFound
        id={id}
        linkURL={urls.machines.index}
        modelName="machine"
      />
    );
  }

  return (
    <PageContent header={<MachineHeader systemId={id} />}>
      <Outlet />
    </PageContent>
  );
};

export default MachineDetails;
