import { useState } from "react";

import { Button } from "@canonical/react-components";

export enum Labels {
  ShowAdvanced = "Show advanced...",
  HideAdvanced = "Hide advanced...",
}

type Props = {
  children: React.ReactNode;
  initialIsShown?: boolean;
  onAfterShow?: () => void;
  onAfterHide?: () => void;
};

const ShowAdvanced = ({
  children,
  initialIsShown,
  onAfterShow,
  onAfterHide,
}: Props): React.ReactElement => {
  const [isAdvancedShown, setIsAdvancedShown] = useState(
    initialIsShown || false
  );

  return (
    <div className="show-advanced u-align--left">
      {!isAdvancedShown ? (
        <Button
          appearance="link"
          data-testid="show-advanced"
          onClick={() => {
            setIsAdvancedShown(true);
            onAfterShow?.();
          }}
          type="button"
        >
          {Labels.ShowAdvanced}
        </Button>
      ) : null}
      {isAdvancedShown ? (
        <Button
          appearance="link"
          data-testid="hide-advanced"
          onClick={() => {
            setIsAdvancedShown(false);
            onAfterHide?.();
          }}
          type="button"
        >
          {Labels.HideAdvanced}
        </Button>
      ) : null}
      <div
        aria-hidden={isAdvancedShown ? "false" : "true"}
        className="show-advanced__content"
      >
        {children}
      </div>
    </div>
  );
};

export default ShowAdvanced;
