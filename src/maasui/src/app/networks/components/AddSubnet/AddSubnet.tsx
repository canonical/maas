import type { ReactElement } from "react";

import { Col, Input, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import FabricSelect from "@/app/base/components/FabricSelect";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import VLANSelect from "@/app/base/components/VLANSelect";
import { useSidePanel } from "@/app/base/side-panel-context";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import { toFormikNumber } from "@/app/utils";

type AddSubnetValues = {
  vlan: string;
  name: string;
  cidr: string;
  gateway_ip: string;
  dns_servers: string;
  fabric: string;
};

const AddSubnetFields = ({ isSaving }: { isSaving: boolean }) => {
  const { values } = useFormikContext<AddSubnetValues>();

  return (
    <>
      <Row>
        <Col size={12}>
          <FormikField
            component={Input}
            disabled={isSaving}
            help="Use IPv4 or IPv6 format"
            label="CIDR"
            name="cidr"
            required
            type="text"
          />
        </Col>
        <Col size={12}>
          <FormikField
            component={Input}
            disabled={isSaving}
            label="Name"
            name="name"
            type="text"
          />
        </Col>
      </Row>
      <Row>
        <Col size={12}>
          <FabricSelect
            defaultOption={null}
            disabled={isSaving}
            name="fabric"
            required
          />
        </Col>
        <Col size={12}>
          <VLANSelect
            defaultOption={null}
            disabled={isSaving}
            fabric={toFormikNumber(values?.fabric)}
            includeDefaultVlan={true}
            name="vlan"
            required
            setDefaultValueFromFabric
          />
        </Col>
      </Row>
      <Row>
        <Col size={12}>
          <FormikField
            component={Input}
            disabled={isSaving}
            help="Use IPv4 or IPv6 format"
            label="DNS servers"
            name="dns_servers"
            type="text"
          />
        </Col>
        <Col size={12}>
          <FormikField
            component={Input}
            disabled={isSaving}
            help="Use IPv4 or IPv6 format"
            label="Gateway IP"
            name="gateway_ip"
            type="text"
          />
        </Col>
      </Row>
    </>
  );
};

const addSubnetSchema = Yup.object()
  .shape({
    cidr: Yup.string().required("CIDR is required"),
    name: Yup.string(),
    fabric: Yup.number(),
    vlan: Yup.number(),
    dns_servers: Yup.string(),
    gateway_ip: Yup.string(),
  })
  .defined();

const AddSubnet = (): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const isSaving = useSelector(subnetSelectors.saving);
  const isSaved = useSelector(subnetSelectors.saved);
  const errors = useSelector(subnetSelectors.errors);

  return (
    <FormikForm<AddSubnetValues>
      aria-label="Add subnet"
      cleanup={subnetActions.cleanup}
      errors={errors}
      initialValues={{
        vlan: "",
        name: "",
        cidr: "",
        gateway_ip: "",
        dns_servers: "",
        fabric: "",
      }}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Add Subnet",
        category: "Subnets form actions",
        label: "Add Subnet",
      }}
      onSubmit={({ cidr, name, fabric, vlan, dns_servers, gateway_ip }) => {
        dispatch(subnetActions.cleanup());
        dispatch(
          subnetActions.create({
            cidr,
            name,
            fabric: toFormikNumber(fabric),
            vlan: toFormikNumber(vlan),
            dns_servers,
            gateway_ip,
          })
        );
      }}
      onSuccess={closeSidePanel}
      saved={isSaved}
      saving={isSaving}
      submitLabel="Save subnet"
      validationSchema={addSubnetSchema}
    >
      <AddSubnetFields isSaving={isSaving} />
    </FormikForm>
  );
};

export default AddSubnet;
