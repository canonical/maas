import { Col, Row } from "@canonical/react-components";

import type { PowerFormValues } from "../PowerForm";

import PowerTypeFields from "@/app/base/components/PowerTypeFields";
import { PowerTypeNames } from "@/app/store/general/constants";
import type { MachineDetails } from "@/app/store/machine/types";
import { getMachineFieldScopes } from "@/app/store/machine/utils";

type Props = {
  machine: MachineDetails;
};

const PowerFormFields = ({ machine }: Props): React.ReactElement => {
  const isMachineInPod = Boolean(machine.pod);
  const fieldScopes = getMachineFieldScopes(machine);

  return (
    <Row>
      <Col size={6}>
        <PowerTypeFields<PowerFormValues>
          customFieldProps={{
            [PowerTypeNames.LXD]: {
              canEditCertificate: !isMachineInPod,
              initialShouldGenerateCert: !machine.certificate,
            },
          }}
          disableSelect={isMachineInPod}
          fieldScopes={fieldScopes}
          powerParametersValueName="powerParameters"
          powerTypeValueName="powerType"
        />
      </Col>
    </Row>
  );
};

export default PowerFormFields;
