import type { ButtonProps } from "@canonical/react-components";
import { Button, Icon } from "@canonical/react-components";
import classNames from "classnames";

const SelectButton = ({
  children,
  className,
  ...props
}: ButtonProps): React.ReactElement => (
  <Button
    {...props}
    className={classNames("p-button--select", className)}
    hasIcon
    type="button"
  >
    {children} <Icon name="chevron-down" />
  </Button>
);

export default SelectButton;
