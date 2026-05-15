import MachineActionMenu from "./MachineActionMenu";
import MachineActionMenuBar from "./MachineActionMenuBar";
import type { MachineActionsProps } from "./types";

const MachineActions = ({
  disabledActions,
  isViewingDetails,
  systemId,
}: MachineActionsProps) => {
  return (
    <>
      <div className="u-hide--medium u-hide--small">
        <MachineActionMenuBar
          disabledActions={disabledActions}
          isViewingDetails={isViewingDetails}
          systemId={systemId}
        />
      </div>
      <div className="u-hide--large">
        <MachineActionMenu
          disabledActions={disabledActions}
          isViewingDetails={isViewingDetails}
          systemId={systemId}
        />
      </div>
    </>
  );
};

export default MachineActions;
