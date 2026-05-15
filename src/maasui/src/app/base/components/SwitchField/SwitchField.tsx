import type { ReactNode } from "react";

import { Field } from "@canonical/react-components";
import classNames from "classnames";

import type { SwitchProps } from "../Switch";
import Switch from "../Switch";

export type Props = SwitchProps & {
  caution?: string;
  className?: string;
  error?: string;
  help?: string;
  id?: string;
  label?: ReactNode;
  labelClassName?: string;
  required?: boolean;
  stacked?: boolean;
  success?: string;
  type?: string;
  wrapperClassName?: string;
};

const SwitchField = ({
  caution,
  className,
  error,
  help,
  id,
  label,
  labelClassName,
  required,
  stacked,
  success,
  wrapperClassName,
  ...props
}: Props): React.ReactElement => {
  return (
    <Field
      caution={caution}
      className={wrapperClassName}
      error={error}
      forId={id}
      help={help}
      label={label}
      labelClassName={labelClassName}
      required={required}
      stacked={stacked}
      success={success}
    >
      <Switch
        className={classNames("p-form-validation__input", className)}
        id={id}
        {...props}
      />
    </Field>
  );
};

export default SwitchField;
