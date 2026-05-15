import { Col, Row } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import type { ZoneResponse } from "@/app/apiclient";
import ActionForm from "@/app/base/components/ActionForm";
import ZoneSelect from "@/app/base/components/ZoneSelect";
import { useSidePanel } from "@/app/base/side-panel-context";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import { kebabToCamelCase } from "@/app/utils";

type Props = {
  devices: Device[];
  isViewingDetails: boolean;
};

type SetZoneFormValues = {
  zone: ZoneResponse["id"] | "";
};

const SetZoneSchema = Yup.object().shape({
  zone: Yup.number().required("Zone is required"),
});

const SetDeviceZoneForm = ({ devices, isViewingDetails }: Props) => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const systemIds = devices.map((device) => device.system_id);
  const errors = useSelector((state: RootState) =>
    deviceSelectors.eventErrorsForDevices(
      state,
      systemIds,
      kebabToCamelCase(NodeActions.SET_ZONE)
    )
  )[0]?.error;
  const settingZone = useSelector(deviceSelectors.settingZone);
  const processingCount = settingZone.length;

  const onSubmit = (zoneId: ZoneResponse["id"]) => {
    systemIds.forEach((systemId) => {
      dispatch(deviceActions.setZone({ system_id: systemId, zone_id: zoneId }));
    });
  };

  return (
    <ActionForm<SetZoneFormValues>
      actionName={NodeActions.SET_ZONE}
      cleanup={deviceActions.cleanup}
      errors={errors}
      initialValues={{
        zone: "",
      }}
      modelName={"device"}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Submit",
        category: `Device ${isViewingDetails ? "details" : "list"} action form`,
        label: "Set zone",
      }}
      onSubmit={(values) => {
        if (values.zone || values.zone === 0) {
          onSubmit(values.zone);
        }
      }}
      onSuccess={closeSidePanel}
      processingCount={processingCount}
      selectedCount={devices.length}
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

export default SetDeviceZoneForm;
