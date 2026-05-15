import { Col, Row } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import type { ZoneResponse } from "@/app/apiclient";
import ActionForm from "@/app/base/components/ActionForm";
import ZoneSelect from "@/app/base/components/ZoneSelect";
import { useSidePanel } from "@/app/base/side-panel-context";
import { getProcessingCount } from "@/app/controllers/utils";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors, {
  statusSelectors,
} from "@/app/store/controller/selectors";
import { ACTIONS } from "@/app/store/controller/slice";
import type { Controller } from "@/app/store/controller/types";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import { kebabToCamelCase } from "@/app/utils";

type Props = {
  controllers: Controller[];
  isViewingDetails: boolean;
};

type SetZoneFormValues = {
  zone: ZoneResponse["id"] | "";
};

const SetZoneSchema = Yup.object().shape({
  zone: Yup.number().required("Zone is required"),
});

const SetControllerZoneForm = ({ controllers, isViewingDetails }: Props) => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const actionStatus = ACTIONS.find(
    ({ name }) => name === NodeActions.SET_ZONE
  )?.status;
  const systemIds = controllers.map((controller) => controller.system_id);
  const errors = useSelector((state: RootState) =>
    controllerSelectors.eventErrorsForControllers(
      state,
      systemIds,
      kebabToCamelCase(NodeActions.SET_ZONE)
    )
  )[0]?.error;
  const processingControllers = useSelector(
    actionStatus ? statusSelectors[actionStatus] : () => []
  );
  const processingCount = getProcessingCount(
    controllers,
    processingControllers
  );

  const onSubmit = (zoneId: ZoneResponse["id"]) => {
    systemIds.forEach((systemId) => {
      dispatch(
        controllerActions.setZone({ system_id: systemId, zone_id: zoneId })
      );
    });
  };

  return (
    <ActionForm<SetZoneFormValues>
      actionName={NodeActions.SET_ZONE}
      cleanup={controllerActions.cleanup}
      errors={errors}
      initialValues={{
        zone: "",
      }}
      modelName={"controller"}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Submit",
        category: `Controller ${
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
      processingCount={processingCount}
      selectedCount={controllers.length}
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

export default SetControllerZoneForm;
