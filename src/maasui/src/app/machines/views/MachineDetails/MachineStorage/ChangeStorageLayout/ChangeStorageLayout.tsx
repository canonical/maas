import type { ReactElement } from "react";

import { Icon } from "@canonical/react-components";
import { useDispatch } from "react-redux";

import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { machineActions } from "@/app/store/machine";
import type { Machine, StorageLayoutOption } from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { StorageLayout } from "@/app/store/types/enum";
import { isVMWareLayout } from "@/app/store/utils";

type ChangeStorageLayoutProps = {
  systemId: Machine["system_id"];
  selectedLayout: StorageLayoutOption;
};

export const ChangeStorageLayout = ({
  systemId,
  selectedLayout,
}: ChangeStorageLayoutProps): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "applyingStorageLayout",
    "applyStorageLayout"
  );

  return (
    <FormikForm<EmptyObject, MachineEventErrors>
      cleanup={machineActions.cleanup}
      errors={errors}
      initialValues={{}}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: `Change storage layout${
          selectedLayout ? ` to ${selectedLayout?.sentenceLabel}` : ""
        }`,
        category: "Machine storage",
        label: "Change storage layout",
      }}
      onSubmit={() => {
        dispatch(machineActions.cleanup());
        dispatch(
          machineActions.applyStorageLayout({
            systemId,
            storageLayout: selectedLayout.value,
          })
        );
        closeSidePanel();
      }}
      saved={saved}
      saving={saving}
      submitAppearance="negative"
      submitLabel="Change storage layout"
    >
      <div className="u-flex">
        <p className="u-nudge-right">
          <Icon name="warning" />
        </p>
        <div className="u-nudge-right">
          <p className="u-no-max-width u-sv1">
            <strong>
              Are you sure you want to change the storage layout to{" "}
              {selectedLayout.sentenceLabel}?
            </strong>
            <br />
            Any changes done already will be lost.
            <br />
            {selectedLayout.value === StorageLayout.BLANK && (
              <>
                Used disks will be returned to available, and any volume groups,
                raid sets, caches, and filesystems removed.
                <br />
              </>
            )}
            {isVMWareLayout(selectedLayout.value) && (
              <>
                This layout allows only for the deployment of{" "}
                <strong>VMware ESXi</strong> images.
                <br />
              </>
            )}
            The storage layout will be applied to a node when it is deployed.
          </p>
        </div>
      </div>
    </FormikForm>
  );
};

export default ChangeStorageLayout;
