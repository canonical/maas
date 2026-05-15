import { Col, Row, Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import { Labels } from "../StaticRoutes";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import SubnetSelect from "@/app/base/components/SubnetSelect";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { RootState } from "@/app/store/root/types";
import { staticRouteActions } from "@/app/store/staticroute";
import staticRouteSelectors from "@/app/store/staticroute/selectors";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import { getIsDestinationForSource } from "@/app/store/subnet/utils";
import { toFormikNumber } from "@/app/utils";

export type AddStaticRouteValues = {
  source: Subnet[SubnetMeta.PK];
  destination: string;
  metric: string;
  gateway_ip: string;
};

export enum AddStaticRouteFormLabels {
  AddStaticRoute = "Add static route",
  Save = "Save",
  Cancel = "Cancel",
}

const addStaticRouteSchema = Yup.object().shape({
  gateway_ip: Yup.string().required("Gateway IP is required"),
  destination: Yup.string().required("Destination is required"),
  metric: Yup.number().required("Metric is required"),
});

export type AddStaticRouteProps = {
  subnetId: Subnet[SubnetMeta.PK];
};

const AddStaticRouteForm = ({
  subnetId,
}: AddStaticRouteProps): React.ReactElement | null => {
  const { closeSidePanel } = useSidePanel();
  const staticRouteErrors = useSelector(staticRouteSelectors.errors);
  const saving = useSelector(staticRouteSelectors.saving);
  const saved = useSelector(staticRouteSelectors.saved);
  const dispatch = useDispatch();
  const staticRoutesLoading = useSelector(staticRouteSelectors.loading);
  const subnetsLoading = useSelector(subnetSelectors.loading);
  const loading = staticRoutesLoading || subnetsLoading;
  const source = useSelector((state: RootState) =>
    subnetSelectors.getById(state, subnetId)
  );

  useFetchActions([subnetActions.fetch]);

  if (loading) {
    return <Spinner text="Loading..." />;
  }

  return (
    <FormikForm<AddStaticRouteValues>
      aria-label={AddStaticRouteFormLabels.AddStaticRoute}
      cleanup={staticRouteActions.cleanup}
      errors={staticRouteErrors}
      initialValues={{
        source: subnetId,
        gateway_ip: "",
        destination: "",
        metric: "0",
      }}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: AddStaticRouteFormLabels.Save,
        category: "Subnet",
        label: AddStaticRouteFormLabels.AddStaticRoute,
      }}
      onSubmit={({ gateway_ip, destination, metric }) => {
        dispatch(staticRouteActions.cleanup());
        dispatch(
          staticRouteActions.create({
            source: subnetId,
            gateway_ip,
            destination: toFormikNumber(destination) as number,
            metric: toFormikNumber(metric),
          })
        );
      }}
      onSuccess={closeSidePanel}
      resetOnSave
      saved={saved}
      saving={saving}
      submitLabel={AddStaticRouteFormLabels.Save}
      validationSchema={addStaticRouteSchema}
    >
      <Row>
        <Col size={12}>
          <FormikField label={Labels.GatewayIp} name="gateway_ip" type="text" />
        </Col>
        <Col size={12}>
          <SubnetSelect
            defaultOption={{
              label: "Select destination",
              value: "",
              disabled: true,
            }}
            filterFunction={(destination) =>
              getIsDestinationForSource(destination, source)
            }
            label={Labels.Destination}
            name="destination"
          />
        </Col>
        <Col size={12}>
          <FormikField label={Labels.Metric} name="metric" type="text" />
        </Col>
      </Row>
    </FormikForm>
  );
};

export default AddStaticRouteForm;
