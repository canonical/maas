import { useCallback } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import type { SchemaOf } from "yup";
import * as Yup from "yup";

import MachineFormFields from "./MachineFormFields";

import Definition from "@/app/base/components/Definition";
import EditableSection from "@/app/base/components/EditableSection";
import FormikForm from "@/app/base/components/FormikForm";
import { useCanEdit } from "@/app/base/hooks";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineDetails } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";

export type MachineFormValues = {
  architecture: MachineDetails["architecture"];
  description: MachineDetails["description"];
  is_dpu: MachineDetails["is_dpu"];
  minHweKernel: MachineDetails["min_hwe_kernel"];
  pool: MachineDetails["pool"]["name"];
  zone: MachineDetails["zone"]["name"];
};

type Props = { systemId: MachineDetails["system_id"] };

const MachineFormSchema: SchemaOf<MachineFormValues> = Yup.object()
  .shape({
    architecture: Yup.string().required("Architecture is required"),
    description: Yup.string(),
    is_dpu: Yup.boolean(),
    minHweKernel: Yup.string(),
    pool: Yup.string().required("Resource pool is required"),
    zone: Yup.string().required("Zone is required"),
  })
  .defined();

const MachineForm = ({ systemId }: Props): React.ReactElement | null => {
  const dispatch = useDispatch();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const errors = useSelector(machineSelectors.errors);
  const saved = useSelector(machineSelectors.saved);
  const saving = useSelector(machineSelectors.saving);
  const cleanup = useCallback(() => machineActions.cleanup(), []);
  const canEdit = useCanEdit(machine, true);

  if (!isMachineDetails(machine)) {
    return <Spinner text="Loading..." />;
  }

  return (
    <EditableSection
      canEdit={canEdit}
      className="u-no-padding--top"
      hasSidebarTitle
      renderContent={(editing, setEditing) =>
        editing ? (
          <FormikForm<MachineFormValues>
            cleanup={cleanup}
            errors={errors}
            initialValues={{
              architecture: machine.architecture || "",
              description: machine.description || "",
              is_dpu: machine.is_dpu || false,
              minHweKernel: machine.min_hwe_kernel || "",
              pool: machine.pool?.name || "",
              zone: machine.zone?.name || "",
            }}
            onCancel={() => {
              setEditing(false);
            }}
            onSaveAnalytics={{
              action: "Configure machine",
              category: "Machine details",
              label: "Save changes",
            }}
            onSubmit={(values) => {
              const params = {
                architecture: values.architecture,
                description: values.description,
                is_dpu: values.is_dpu,
                extra_macs: machine.extra_macs,
                pxe_mac: machine.pxe_mac,
                min_hwe_kernel: values.minHweKernel,
                pool: { name: values.pool },
                system_id: machine.system_id,
                zone: { name: values.zone },
              };
              dispatch(machineActions.update(params));
            }}
            onSuccess={() => {
              setEditing(false);
            }}
            saved={saved}
            saving={saving}
            submitLabel="Save changes"
            validationSchema={MachineFormSchema}
          >
            <MachineFormFields />
          </FormikForm>
        ) : (
          <div data-testid="machine-details">
            <Definition
              description={machine.architecture}
              label="Architecture"
            />
            <Definition
              description={machine.min_hwe_kernel}
              label="Minimum kernel"
            />
            <Definition description={machine.zone.name} label="Zone" />
            <Definition description={machine.pool.name} label="Resource pool" />
            <Definition
              children={machine.is_dpu ? "True" : "False"}
              label={"Registered as DPU"}
            />
            <Definition description={machine.description} label="Note" />
          </div>
        )
      }
      title="Machine configuration"
    />
  );
};

export default MachineForm;
