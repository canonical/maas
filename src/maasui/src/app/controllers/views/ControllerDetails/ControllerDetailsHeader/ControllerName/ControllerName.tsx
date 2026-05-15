import { useDispatch, useSelector } from "react-redux";

import NodeName from "@/app/base/components/NodeName";
import { useFetchActions } from "@/app/base/hooks";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller } from "@/app/store/controller/types";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";
import type { RootState } from "@/app/store/root/types";

type Props = {
  id: Controller["system_id"];
  isEditing: boolean;
  setIsEditing: (editingName: boolean) => void;
};

const ControllerName = ({
  id,
  isEditing,
  setIsEditing,
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, id)
  );
  const saved = useSelector(controllerSelectors.saved);
  const saving = useSelector(controllerSelectors.saving);
  const domains = useSelector(domainSelectors.all);

  useFetchActions([domainActions.fetch]);

  return (
    <NodeName
      editingName={isEditing}
      node={controller}
      onSubmit={(_hostname, domain) => {
        if (controller) {
          dispatch(
            controllerActions.update({
              domain: domains.find(({ id }) => id === domain),
              system_id: controller.system_id,
            })
          );
        }
      }}
      saved={saved}
      saving={saving}
      setEditingName={setIsEditing}
    />
  );
};

export default ControllerName;
