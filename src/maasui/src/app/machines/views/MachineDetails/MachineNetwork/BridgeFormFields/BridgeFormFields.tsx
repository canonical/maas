import { Col, Row, Select } from "@canonical/react-components";
import { useFormikContext } from "formik";

import type { BridgeFormValues } from "../AddBridgeForm/types";
import NetworkFields from "../NetworkFields";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import MacAddressField from "@/app/base/components/MacAddressField";
import SwitchField from "@/app/base/components/SwitchField";
import TagNameField from "@/app/base/components/TagNameField";
import TooltipButton from "@/app/base/components/TooltipButton";
import { BridgeType, NetworkInterfaceTypes } from "@/app/store/types/enum";

type Props = {
  typeDisabled?: boolean;
};

const BridgeFormFields = ({
  typeDisabled,
}: Props): React.ReactElement | null => {
  const { setFieldValue, values } = useFormikContext<BridgeFormValues>();

  return (
    <Row>
      <Col size={12}>
        <h3 className="p-heading--5 u-no-margin--bottom">Bridge details</h3>
        <FormikField label="Bridge name" name="name" type="text" />
        <FormikField
          component={Select}
          disabled={typeDisabled}
          label="Bridge type"
          name="bridge_type"
          options={[
            { label: "Standard", value: BridgeType.STANDARD },
            { label: "Open vSwitch (ovs)", value: BridgeType.OVS },
          ]}
          required
        />
        <MacAddressField label="MAC address" name="mac_address" required />
        <TagNameField className="u-sv2" />
        <h3 className="p-heading--5 u-no-margin--bottom">Advanced options</h3>
        <FormikField
          aria-label="STP"
          component={SwitchField}
          label={
            <>
              STP{" "}
              <TooltipButton
                iconName="help"
                message="Controls the participation of this bridge in the spanning tree protocol."
                position="top-left"
              />
            </>
          }
          name="bridge_stp"
          onChange={(evt: React.ChangeEvent<HTMLInputElement>) => {
            const { checked } = evt.target;
            // Manually set the value because we've overwritten the onChange.
            setFieldValue("bridge_stp", checked).catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "bridge_stp",
                "setFieldValue",
                reason as string
              );
            });
            // Set an initial value for the fd field or clear the current value.
            if (checked) {
              setFieldValue("bridge_fd", 15).catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "bridge_fd",
                  "setFieldValue",
                  reason as string
                );
              });
            } else {
              setFieldValue("bridge_fd", "").catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "bridge_fd",
                  "setFieldValue",
                  reason as string
                );
              });
            }
          }}
          type="checkbox"
        />
        {values.bridge_stp ? (
          <FormikField
            label="Forward delay (ms)"
            name="bridge_fd"
            type="text"
          />
        ) : null}
      </Col>
      <Col size={12}>
        <h3 className="p-heading--5 u-no-margin--bottom">Network</h3>
        <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
      </Col>
    </Row>
  );
};

export default BridgeFormFields;
