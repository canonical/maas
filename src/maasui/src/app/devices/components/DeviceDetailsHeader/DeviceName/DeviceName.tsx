import { useDispatch, useSelector } from "react-redux";

import NodeName from "@/app/base/components/NodeName";
import { useFetchActions } from "@/app/base/hooks";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device } from "@/app/store/device/types";
import { DeviceMeta } from "@/app/store/device/types";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";
import type { RootState } from "@/app/store/root/types";

type Props = {
  editingName: boolean;
  id: Device["system_id"];
  setEditingName: (editingName: boolean) => void;
};

const DeviceName = ({
  editingName,
  id,
  setEditingName,
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const device = useSelector((state: RootState) =>
    deviceSelectors.getById(state, id)
  );
  const saved = useSelector(deviceSelectors.saved);
  const saving = useSelector(deviceSelectors.saving);
  const domains = useSelector(domainSelectors.all);

  useFetchActions([domainActions.fetch]);

  return (
    <NodeName
      editingName={editingName}
      node={device}
      onSubmit={(hostname, domain) => {
        if (device) {
          dispatch(
            deviceActions.update({
              domain: domains.find(({ id }) => id === domain),
              hostname,
              [DeviceMeta.PK]: device[DeviceMeta.PK],
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

export default DeviceName;
