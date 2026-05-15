import { useEffect } from "react";

import { Col, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { CredentialsFormValues } from "../../types";

import CertificateFields from "@/app/base/components/CertificateFields";
import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import ResourcePoolSelect from "@/app/base/components/ResourcePoolSelect";
import ZoneSelect from "@/app/base/components/ZoneSelect";
import podSelectors from "@/app/store/pod/selectors";

type Props = {
  setShouldGenerateCert: (generateCert: boolean) => void;
  shouldGenerateCert: boolean;
};

export const CredentialsFormFields = ({
  setShouldGenerateCert,
  shouldGenerateCert,
}: Props): React.ReactElement => {
  const lxdAddresses = useSelector(podSelectors.groupByLxdServer).map(
    (group) => group.address
  );
  const { setFieldValue, setFieldTouched } =
    useFormikContext<CredentialsFormValues>();

  useEffect(() => {
    // The validation schema changes depending on the state of
    // `shouldGenerateCert`. Here we touch the fields so that the new validation
    // is applied to the fields that changed.
    setFieldTouched("certificate").catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "certificate",
        "setFieldTouched",
        reason as string
      );
    });
    setFieldTouched("key").catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "key",
        "setFieldTouched",
        reason as string
      );
    });
  }, [shouldGenerateCert, setFieldTouched]);

  return (
    <Row>
      <Col size={12}>
        <FormikField label="Name" name="name" required type="text" />
        <ZoneSelect name="zone" required valueKey="id" />
        <ResourcePoolSelect name="pool" required valueKey="id" />
        <FormikField
          autoComplete="off"
          label="LXD address"
          list="lxd-addresses"
          name="power_address"
          required
          type="text"
        />
        <datalist id="lxd-addresses">
          {lxdAddresses.map((address) => (
            <option key={address} value={address}>
              {address}
            </option>
          ))}
        </datalist>
        <CertificateFields
          onShouldGenerateCert={(shouldGenerateCert) => {
            setShouldGenerateCert(shouldGenerateCert);
            setFieldValue("certificate", "").catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "certificate",
                "setFieldValue",
                reason as string
              );
            });
            setFieldValue("key", "").catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "key",
                "setFieldValue",
                reason as string
              );
            });
          }}
          shouldGenerateCert={shouldGenerateCert}
        />
      </Col>
    </Row>
  );
};

export default CredentialsFormFields;
