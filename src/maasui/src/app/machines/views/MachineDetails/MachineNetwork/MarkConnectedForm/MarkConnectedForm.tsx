import type { ReactElement, ReactNode } from "react";
import { useState } from "react";

import { useDispatch, useSelector } from "react-redux";

import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import { getLinkInterface } from "@/app/store/utils";

export enum ConnectionState {
  DISCONNECTED_WARNING = "disconnectedWarning",
  MARK_CONNECTED = "markConnected",
  MARK_DISCONNECTED = "markDisconnected",
}

type MarkConnectedProps = {
  systemId: MachineDetails["system_id"];
  link?: NetworkLink | null;
  nic?: NetworkInterface | null;
  connectionState: ConnectionState;
};

const MarkConnectedForm = ({
  systemId,
  nic,
  link,
  connectionState,
}: MarkConnectedProps): ReactElement | null => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const [saved, setSaved] = useState(false);
  if (machine && link && !nic) {
    [nic] = getLinkInterface(machine, link);
  }
  if (!machine || !nic) {
    return null;
  }
  const showDisconnectedWarning =
    connectionState === ConnectionState.DISCONNECTED_WARNING;
  const markConnected =
    connectionState === ConnectionState.MARK_CONNECTED ||
    showDisconnectedWarning;
  const event = markConnected ? "connected" : "disconnected";
  let message: ReactNode;
  const updateConnection = () => {
    if (nic?.id) {
      dispatch(
        machineActions.updateInterface({
          interface_id: nic?.id,
          link_connected: !!markConnected,
          system_id: machine.system_id,
        })
      );
    }
    setSaved(true);
  };

  if (showDisconnectedWarning) {
    message = (
      <>
        This interface is <strong>disconnected</strong>, it cannot be configured
        unless a cable is connected.
        <br />
        If this is no longer true, mark cable as connected.
      </>
    );
  } else {
    message = (
      <>
        This interface was detected as{" "}
        <strong>{nic.link_connected ? "connected" : "disconnected"}</strong>.
        Are you sure you want to mark it as {event}?
        {markConnected ? null : (
          <>
            <br />
            When the interface is disconnected, it cannot be configured.
          </>
        )}
      </>
    );
  }

  return (
    <ModelActionForm
      aria-label={`Mark ${event}`}
      initialValues={{}}
      message={message}
      modelType="interface"
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: `Mark interface as ${event}`,
        category: "Machine network",
        label: "Update",
      }}
      onSubmit={updateConnection}
      onSuccess={closeSidePanel}
      saved={saved}
      submitAppearance={markConnected ? "positive" : "negative"}
      submitLabel={`Mark as ${event}`}
    />
  );
};

export default MarkConnectedForm;
