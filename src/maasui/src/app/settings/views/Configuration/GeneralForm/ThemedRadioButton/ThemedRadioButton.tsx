import type { ReactNode, MouseEventHandler } from "react";

import classNames from "classnames";
import type { JSX } from "react/jsx-runtime";

export type Props = React.PropsWithoutRef<JSX.IntrinsicElements["input"]> & {
  checked?: boolean;
  className?: string;
  color?: ColorValues;
  name?: string;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  label?: ReactNode;
};

export enum ColorValues {
  Default = "default",
  Bark = "bark",
  Sage = "sage",
  Olive = "olive",
  Viridian = "viridian",
  PrussianGreen = "prussian_green",
  Blue = "blue",
  Purple = "purple",
  Magenta = "magenta",
  Red = "red",
}

const ThemedRadioButton = ({
  className,
  color,
  label,
  name,
  onClick,
  value,
  ...inputProps
}: Props): React.ReactElement => {
  return (
    <label className={classNames(className, "general-form__radio--themed")}>
      <input
        className={`general-form__radio is-maas-${color}`}
        defaultChecked={value === color}
        name={name}
        type="radio"
        {...inputProps}
        onClick={onClick}
        value={color}
      />
      {label}
    </label>
  );
};

export default ThemedRadioButton;
