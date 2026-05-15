import type { ReactNode } from "react";

import type {
  ButtonProps,
  IconProps,
  SubComponentProps,
  TooltipProps,
} from "@canonical/react-components";
import { Button, Icon, Tooltip } from "@canonical/react-components";

import { breakLines, unindentString } from "@/app/utils";

type Props = Omit<TooltipProps, "aria-label" | "children"> & {
  "aria-label"?: ButtonProps["aria-label"];
  buttonProps?: SubComponentProps<Omit<ButtonProps, "aria-label">>;
  children?: ReactNode;
  iconName?: IconProps["name"];
  iconProps?: SubComponentProps<Omit<IconProps, "name">>;
};

const TooltipButton = ({
  "aria-label": ariaLabel,
  buttonProps,
  children,
  iconName = "information",
  iconProps,
  message,
  ...tooltipProps
}: Props): React.ReactElement => {
  return (
    <Tooltip
      message={
        typeof message === "string"
          ? breakLines(unindentString(message))
          : message
      }
      {...tooltipProps}
    >
      <Button
        appearance="base"
        aria-label={ariaLabel}
        className="u-no-border u-no-line-height u-no-margin"
        hasIcon
        small
        type="button"
        {...buttonProps}
      >
        {typeof children === "string" ? <span>{children}</span> : children}
        {iconName ? (
          <Icon aria-label={iconName} name={iconName} {...iconProps} />
        ) : null}
      </Button>
    </Tooltip>
  );
};

export default TooltipButton;
