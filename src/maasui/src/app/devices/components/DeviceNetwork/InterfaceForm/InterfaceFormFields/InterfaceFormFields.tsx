import type { ChangeEvent } from "react";

import { Col, Input, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";

import type { InterfaceFormValues } from "../InterfaceForm";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import IpAssignmentSelect from "@/app/base/components/IpAssignmentSelect";
import MacAddressField from "@/app/base/components/MacAddressField";
import SubnetSelect from "@/app/base/components/SubnetSelect";
import TagNameField from "@/app/base/components/TagNameField";
import { DeviceIpAssignment } from "@/app/store/device/types";

type Props = {
  showTitles?: boolean;
};

const InterfaceFormFields = ({
  showTitles = false,
}: Props): React.ReactElement => {
  const { handleChange, setFieldValue, values } =
    useFormikContext<InterfaceFormValues>();
  const showSubnetField = values.ip_assignment === DeviceIpAssignment.STATIC;
  const showIpAddressField =
    values.ip_assignment === DeviceIpAssignment.STATIC ||
    values.ip_assignment === DeviceIpAssignment.EXTERNAL;

  const nameField = <FormikField label="Name" name="name" type="text" />;

  return (
    <>
      {showTitles ? null : (
        <>
          <Row>
            <Col size={12}>{nameField}</Col>
          </Row>
          <hr />
        </>
      )}
      <Row>
        <Col size={12}>
          {showTitles ? (
            <>
              <h3
                className="p-heading--5 u-no-margin--bottom"
                data-testid="interface-form-heading"
              >
                Physical details
              </h3>
              {nameField}
            </>
          ) : null}
          <Input
            aria-label="Type"
            disabled
            label="Type"
            name="type"
            type="text"
            value="Physical"
          />
          <MacAddressField label="MAC address" name="mac_address" />
          <TagNameField name="tags" />
        </Col>
        <Col size={12}>
          {showTitles ? (
            <h3
              className="p-heading--5 u-no-margin--bottom"
              data-testid="interface-form-heading"
            >
              Network
            </h3>
          ) : null}
          <IpAssignmentSelect
            data-testid="ip-assignment-field"
            name="ip_assignment"
            onChange={(e: ChangeEvent<HTMLSelectElement>) => {
              handleChange(e);
              setFieldValue("subnet", "").catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "subnet",
                  "setFieldValue",
                  reason as string
                );
              });
              setFieldValue("ip_address", "").catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "ip_address",
                  "setFieldValue",
                  reason as string
                );
              });
            }}
          />
          {showSubnetField && (
            <SubnetSelect data-testid="subnet-field" name="subnet" />
          )}
          {showIpAddressField && (
            <FormikField
              data-testid="ip-address-field"
              label="IP address"
              name="ip_address"
              type="text"
            />
          )}
        </Col>
      </Row>
    </>
  );
};

export default InterfaceFormFields;
