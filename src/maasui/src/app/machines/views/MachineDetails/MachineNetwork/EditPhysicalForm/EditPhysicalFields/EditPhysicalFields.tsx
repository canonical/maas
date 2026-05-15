import { Col, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";

import NetworkFields from "../../NetworkFields";
import type { EditPhysicalValues } from "../types";

import FormikField from "@/app/base/components/FormikField";
import MacAddressField from "@/app/base/components/MacAddressField";
import TagNameField from "@/app/base/components/TagNameField";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { NetworkInterface } from "@/app/store/types/node";

type Props = {
  nic: NetworkInterface | null;
};

const generateCaution = (values: EditPhysicalValues) =>
  values.link_speed > values.interface_speed
    ? "Link speed should not be higher than interface speed"
    : null;

const EditPhysicalFields = ({ nic }: Props): React.ReactElement | null => {
  const { values } = useFormikContext<EditPhysicalValues>();
  if (!nic) {
    return null;
  }
  return (
    <Row>
      <Col size={12}>
        <h3 className="p-heading--5 u-no-margin--bottom">Physical details</h3>
        <FormikField label="Name" name="name" type="text" />
        <MacAddressField label="MAC address" name="mac_address" />
        <TagNameField />
        <FormikField
          caution={generateCaution(values)}
          disabled={!nic.link_connected}
          label="Link speed (Gbps)"
          name="link_speed"
          type="text"
        />
        <FormikField
          disabled={!nic.link_connected}
          label="Interface speed (Gbps)"
          name="interface_speed"
          type="text"
        />
      </Col>
      <Col size={12}>
        <h3 className="p-heading--5 u-no-margin--bottom">Network</h3>
        <NetworkFields editing interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Col>
    </Row>
  );
};

export default EditPhysicalFields;
