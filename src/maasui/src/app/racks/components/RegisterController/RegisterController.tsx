import { useState, type ReactElement } from "react";

import {
  Notification as NotificationBanner,
  RadioInput,
} from "@canonical/react-components";
import { position } from "@canonical/react-components/dist/components/Tooltip";

import GuidedProvisioning from "./components/GuidedProvisioning";
import OneTouchProvisioning from "./components/OneTouchProvisioning";

import TooltipButton from "@/app/base/components/TooltipButton";

type RegisterControllerProps = {
  id: number;
};

const RegisterController = ({ id }: RegisterControllerProps): ReactElement => {
  const [isGuidedProvisioning, setIsGuidedProvisioning] = useState(true);

  return (
    <div>
      <NotificationBanner severity="information" title="Network configuration">
        The controller must be reachable over HTTP to register.
      </NotificationBanner>
      To register a controller to the rack, choose either "guided provisioning"
      or "one-touch provisioning" depending on the controller setup.
      <span className="u-flex--row u-flex--between">
        <RadioInput
          checked={isGuidedProvisioning}
          inline={true}
          label={
            <>
              Guided provisioning{" "}
              <TooltipButton
                iconName="help-mid-dark"
                message="Guided provisioning is used to register controllers during MAAS agent installation."
                position={position.btmLeft}
              />
            </>
          }
          onClick={() => {
            setIsGuidedProvisioning(true);
          }}
        ></RadioInput>
        <RadioInput
          checked={!isGuidedProvisioning}
          inline={true}
          label={
            <>
              One-touch provisioning{" "}
              <TooltipButton
                iconName="help-mid-dark"
                message="One-touch provisioning is used to register controllers with MAAS agent pre-installed."
                position={position.btmLeft}
              />
            </>
          }
          onClick={() => {
            setIsGuidedProvisioning(false);
          }}
        ></RadioInput>
      </span>
      <hr />
      {isGuidedProvisioning ? (
        <GuidedProvisioning id={id} />
      ) : (
        <OneTouchProvisioning />
      )}
    </div>
  );
};

export default RegisterController;
