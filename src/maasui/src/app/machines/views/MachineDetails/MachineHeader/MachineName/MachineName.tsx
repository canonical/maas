import { useDispatch, useSelector } from "react-redux";

import NodeName from "@/app/base/components/NodeName";
import { useFetchActions } from "@/app/base/hooks";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  editingName: boolean;
  id: Machine["system_id"];
  setEditingName: (editingName: boolean) => void;
};

const MachineName = ({
  editingName,
  id,
  setEditingName,
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  const saved = useSelector(machineSelectors.saved);
  const saving = useSelector(machineSelectors.saving);
  const domains = useSelector(domainSelectors.all);

  useFetchActions([domainActions.fetch]);

  return (
    <NodeName
      editingName={editingName}
      node={machine}
      onSubmit={(hostname, domain) => {
        if (machine) {
          dispatch(
            machineActions.update({
              domain: domains.find(({ id }) => id === domain),
              extra_macs: machine.extra_macs,
              hostname,
              pxe_mac: machine.pxe_mac,
              system_id: machine.system_id,
            })
          );
        }
      }}
      saved={saved}
      saving={saving}
      setEditingName={setEditingName}
    />
  );
};

export default MachineName;
