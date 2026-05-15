import { useEffect, useRef } from "react";

import { Col, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { CloneFormValues } from "../CloneForm";

import CloneNetworkTable from "./CloneNetworkTable";
import CloneStorageTable from "./CloneStorageTable";
import SourceMachineSelect from "./SourceMachineSelect";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import { useFetchActions } from "@/app/base/hooks";
import { fabricActions } from "@/app/store/fabric";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineDetails } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import { useFetchMachine } from "@/app/store/machine/utils/hooks";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import { vlanActions } from "@/app/store/vlan";

type Props = {
  selectedMachine: MachineDetails | null;
  setSelectedMachine: (machine: MachineDetails | null) => void;
};

export const CloneFormFields = ({
  selectedMachine,
  setSelectedMachine,
}: Props): React.ReactElement => {
  const { setFieldValue, values } = useFormikContext<CloneFormValues>();
  const cloneNetworkTableContainerRef = useRef<HTMLDivElement>(null);
  const cloneStorageTableContainerRef = useRef<HTMLDivElement>(null);

  const machineInState = useSelector((state: RootState) =>
    machineSelectors.getById(state, values.source)
  );
  const { loading: loadingMachineDetails } = useFetchMachine(values.source);

  useFetchActions([
    fabricActions.fetch,
    subnetActions.fetch,
    vlanActions.fetch,
  ]);

  // The machine in state can change between types Machine and MachineDetails at
  // any time if it's not the "active" machine, so we set the MachineDetails
  // version in local state when it's available. This would not be necessary
  // if it were possible to set more than one machine as "active" at a time.
  // https://bugs.launchpad.net/maas/+bug/1939078
  useEffect(() => {
    if (!selectedMachine && isMachineDetails(machineInState)) {
      setSelectedMachine(machineInState);
    }
  }, [machineInState, selectedMachine, setSelectedMachine]);

  return (
    <div>
      <Row>
        <Col size={12}>
          <p className="source-label">1. Select the source machine</p>
          <SourceMachineSelect
            onMachineClick={(machine) => {
              if (machine) {
                setFieldValue("source", machine.system_id).catch(
                  (reason: unknown) => {
                    throw new FormikFieldChangeError(
                      "source",
                      "setFieldValue",
                      reason as string
                    );
                  }
                );
              } else {
                setFieldValue("source", "").catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "source",
                    "setFieldValue",
                    reason as string
                  );
                });
                setFieldValue("interfaces", false).catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "interfaces",
                    "setFieldValue",
                    reason as string
                  );
                });
                setFieldValue("storage", false).catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "storage",
                    "setFieldValue",
                    reason as string
                  );
                });
                setSelectedMachine(null);
              }
            }}
            selectedMachine={selectedMachine}
          />
        </Col>
      </Row>
      <Row>
        <Col size={12}>
          <p className="clone-label">2. Select what to clone</p>
          <div className="clone-tables">
            <div className="clone-table-card">
              <FormikField
                disabled={!selectedMachine}
                label="Clone network configuration"
                name="interfaces"
                type="checkbox"
                wrapperClassName="u-sv2"
              />
              <div
                className="clone-table-container"
                ref={cloneNetworkTableContainerRef}
              >
                <CloneNetworkTable
                  containerRef={cloneNetworkTableContainerRef}
                  loadingMachineDetails={loadingMachineDetails}
                  machine={selectedMachine}
                  selected={values.interfaces}
                />
              </div>
            </div>
            <div className="clone-table-card">
              <FormikField
                disabled={!selectedMachine}
                label="Clone storage configuration"
                name="storage"
                type="checkbox"
                wrapperClassName="u-sv2"
              />
              <div
                className="clone-table-container"
                ref={cloneStorageTableContainerRef}
              >
                <CloneStorageTable
                  containerRef={cloneStorageTableContainerRef}
                  loadingMachineDetails={loadingMachineDetails}
                  machine={selectedMachine}
                  selected={values.storage}
                />
              </div>
            </div>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default CloneFormFields;
