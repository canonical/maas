import type {
  ComponentProps,
  ComponentType,
  ElementType,
  HTMLProps,
} from "react";

import { Input } from "@canonical/react-components";
import { useField } from "formik";

import { useId } from "@/app/base/hooks/base";

export type Props<C extends ComponentType | ElementType = typeof Input> =
  ComponentProps<C> & {
    component?: C;
    displayError?: boolean;
    name: string;
    value?: HTMLProps<HTMLElement>["value"];
  };

export class FormikFieldChangeError extends Error {
  constructor(fieldName: string, operation: string, reason: string) {
    super(`Formik ${operation} failed for field "${fieldName}": ${reason}`);
    this.name = "FormikFieldChangeError";
    this.cause = `${fieldName}:${operation}`;
  }
}

const FormikField = <C extends ComponentType | ElementType = typeof Input>({
  component: Component = Input,
  displayError = true,
  name,
  value,
  label,
  ...props
}: Props<C>): React.ReactElement => {
  const id = useId();
  const [field, meta] = useField({ name, type: props.type, value });
  return (
    <Component
      aria-label={label}
      error={meta.touched && displayError ? meta.error : null}
      id={id}
      label={label}
      {...field}
      {...props}
    />
  );
};

export default FormikField;
