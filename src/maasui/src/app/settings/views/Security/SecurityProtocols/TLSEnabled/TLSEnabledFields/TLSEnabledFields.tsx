import { ExternalLink } from "@canonical/maas-react-components";
import { Slider } from "@canonical/react-components";
import { useFormikContext } from "formik";

import type { TLSEnabledValues } from "../TLSEnabled";
import { Labels } from "../TLSEnabled";

import FormikField from "@/app/base/components/FormikField";
import docsUrls from "@/app/base/docsUrls";
import { TLSExpiryNotificationInterval } from "@/app/store/config/types";

const TLSEnabledFields = (): React.ReactElement => {
  const { setFieldValue, values } = useFormikContext<TLSEnabledValues>();

  return (
    <>
      <FormikField
        label={Labels.NotificationCheckbox}
        name="notificationEnabled"
        type="checkbox"
      />
      <div className="p-slider--inline">
        <FormikField<typeof Slider>
          component={Slider}
          disabled={!values.notificationEnabled}
          help={
            <>
              <span>{TLSExpiryNotificationInterval.MIN}</span>
              <span>{TLSExpiryNotificationInterval.MAX}</span>
            </>
          }
          label={Labels.Interval}
          max={TLSExpiryNotificationInterval.MAX}
          min={TLSExpiryNotificationInterval.MIN}
          name="notificationInterval"
          onChange={(e) =>
            setFieldValue("notificationInterval", e.target.value)
          }
          showInput
          step={1}
          value={values.notificationInterval}
        />
      </div>
      <p>
        <ExternalLink to={docsUrls.autoRenewTLSCert}>
          How to set up auto-renew for certificates
        </ExternalLink>
      </p>
    </>
  );
};

export default TLSEnabledFields;
