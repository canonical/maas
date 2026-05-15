import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import DoubleRow from "@/app/base/components/DoubleRow";
import PowerIcon from "@/app/base/components/PowerIcon";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import { isTransientStatus, useFormattedOS } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId: Machine["system_id"];
};

const StatusColumn = ({ systemId }: Props): React.ReactElement => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const formattedOS = useFormattedOS(machine, true);

  if (!machine) {
    return <Spinner />;
  }
  const showSpinner = isTransientStatus(machine.status_code);
  return (
    <DoubleRow
      icon={
        <PowerIcon powerState={machine.power_state} showSpinner={showSpinner} />
      }
      primary={machine.status}
      primaryTitle={machine.status}
      secondary={formattedOS}
      secondaryTitle={formattedOS}
    />
  );
};

export default StatusColumn;
