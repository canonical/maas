import type { ReactNode } from "react";

import { Icon } from "@canonical/react-components";
import classNames from "classnames";

import { PowerState } from "@/app/store/types/enum";

type Props = {
  children?: ReactNode;
  className?: string;
  powerState: PowerState;
  showSpinner?: boolean;
};

const getIconName = (powerState: PowerState, showSpinner?: boolean): string => {
  if (showSpinner) {
    return "spinner";
  }
  switch (powerState) {
    case PowerState.ERROR:
      return "power-error";
    case PowerState.OFF:
      return "power-off";
    case PowerState.ON:
      return "power-on";
    case PowerState.UNKNOWN:
      return "power-unknown";
    default:
      return "power-unknown";
  }
};

const PowerIcon = ({
  children,
  className,
  powerState,
  showSpinner,
}: Props): React.ReactElement => {
  const iconClass = classNames(className, {
    "is-inline": Boolean(children),
    "u-animation--spin": showSpinner,
  });
  const iconName = getIconName(powerState, showSpinner);

  return (
    <span>
      <Icon
        aria-label={showSpinner ? "loading" : powerState}
        className={iconClass}
        name={iconName}
      />
      {children}
    </span>
  );
};

export default PowerIcon;
