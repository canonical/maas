import { useFormikContext } from "formik";

import FormikField from "@/app/base/components/FormikField";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import { formatMacAddress } from "@/app/utils";

type Props = FormikFieldProps;

export const MacAddressField = ({
  name,
  ...props
}: Props): React.ReactElement => {
  const formikProps = useFormikContext();
  const { setFieldValue } = formikProps;

  return (
    <FormikField
      name={name}
      onChange={(evt: React.ChangeEvent<HTMLInputElement>) => {
        setFieldValue(name, formatMacAddress(evt.target.value)).catch(
          (reason: unknown) => {
            throw new FormikFieldChangeError(
              name,
              "setFieldValue",
              reason as string
            );
          }
        );
      }}
      placeholder="00:00:00:00:00:00"
      type="text"
      {...props}
    />
  );
};

export default MacAddressField;
