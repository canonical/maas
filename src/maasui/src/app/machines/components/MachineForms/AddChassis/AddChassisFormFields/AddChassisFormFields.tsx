import { Col, Row } from "@canonical/react-components";

import DomainSelect from "@/app/base/components/DomainSelect";
import PowerTypeFields from "@/app/base/components/PowerTypeFields";
import { PowerFieldScope } from "@/app/store/general/types";

export const AddChassisFormFields = (): React.ReactElement => {
  return (
    <>
      <Row>
        <Col size={12}>
          <DomainSelect name="domain" required />
        </Col>
      </Row>
      <Row>
        <Col size={12}>
          <PowerTypeFields fieldScopes={[PowerFieldScope.BMC]} forChassis />
        </Col>
      </Row>
    </>
  );
};

export default AddChassisFormFields;
