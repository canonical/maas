import { Col, Row } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import type { ZoneResponse } from "@/app/apiclient";
import ActionForm from "@/app/base/components/ActionForm";
import ZoneSelect from "@/app/base/components/ZoneSelect";
import { useSidePanel } from "@/app/base/side-panel-context";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineEventErrors } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import {
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import { NodeActions } from "@/app/store/types/node";

type Props = {
  isViewingDetails: boolean;
};

type SetZoneFormValues = {
  zone: ZoneResponse["id"] | "";
};

const SetZoneSchema = Yup.object().shape({
  zone: Yup.number().required("Zone is required"),
});

const SetMachineZoneForm = ({ isViewingDetails }: Props) => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const selectedMachines = useSelector(machineSelectors.selected);
  const searchFilter = FilterMachines.filtersToString(
    FilterMachines.queryStringToFilters(location.search)
  );
  const { selectedCount } = useMachineSelectedCount(
    FilterMachines.parseFetchFilters(searchFilter)
  );
  const {
    dispatch: dispatchForSelectedMachines,
    actionStatus,
    actionErrors,
  } = useSelectedMachinesActionsDispatch({ selectedMachines, searchFilter });

  const onSubmit = (zoneID: ZoneResponse["id"]) => {
    dispatch(machineActions.cleanup());
    dispatchForSelectedMachines(machineActions.setZone, {
      zone_id: zoneID,
    });
  };

  return (
    <ActionForm<SetZoneFormValues, MachineEventErrors>
      actionName={NodeActions.SET_ZONE}
      actionStatus={actionStatus}
      cleanup={machineActions.cleanup}
      errors={actionErrors}
      initialValues={{
        zone: "",
      }}
      modelName={"machine"}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Submit",
        category: `Machine ${
          isViewingDetails ? "details" : "list"
        } action form`,
        label: "Set zone",
      }}
      onSubmit={(values) => {
        if (values.zone || values.zone === 0) {
          onSubmit(values.zone);
        }
      }}
      onSuccess={closeSidePanel}
      selectedCount={selectedCount ?? 0}
      validationSchema={SetZoneSchema}
    >
      <Row>
        <Col size={12}>
          <ZoneSelect name="zone" required valueKey="id" />
        </Col>
      </Row>
    </ActionForm>
  );
};

export default SetMachineZoneForm;
