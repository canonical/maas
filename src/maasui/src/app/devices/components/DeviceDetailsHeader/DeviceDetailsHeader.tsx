import { useState } from "react";

import { useSelector } from "react-redux";
import { Link, useLocation } from "react-router";

import DeviceName from "./DeviceName";

import NodeActionMenu from "@/app/base/components/NodeActionMenu";
import SectionHeader from "@/app/base/components/SectionHeader";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import { DeviceActionFormWrapper } from "@/app/devices/components";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device } from "@/app/store/device/types";
import { isDeviceDetails } from "@/app/store/device/utils";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";

type Props = {
  systemId: Device["system_id"];
};

const DeviceDetailsHeader = ({ systemId }: Props): React.ReactElement => {
  const { openSidePanel } = useSidePanel();
  const [editingName, setEditingName] = useState(false);
  const device = useSelector((state: RootState) =>
    deviceSelectors.getById(state, systemId)
  );
  const { pathname } = useLocation();

  if (!device) {
    return <SectionHeader loading />;
  }

  return (
    <SectionHeader
      buttons={[
        <NodeActionMenu
          filterActions
          hasSelection={true}
          nodeDisplay="device"
          nodes={[device]}
          onActionClick={(action) => {
            openSidePanel({
              component: DeviceActionFormWrapper,
              title: action === NodeActions.DELETE ? "Delete" : "Set zone",
              props: {
                action:
                  action === NodeActions.DELETE ? action : NodeActions.SET_ZONE,
                devices: [device],
                viewingDetails: false,
              },
            });
          }}
        />,
      ]}
      subtitleLoading={!isDeviceDetails(device)}
      tabLinks={[
        {
          active: pathname.startsWith(
            urls.devices.device.summary({ id: systemId })
          ),
          component: Link,
          label: "Summary",
          to: urls.devices.device.summary({ id: systemId }),
        },
        {
          active: pathname.startsWith(
            urls.devices.device.network({ id: systemId })
          ),
          component: Link,
          label: "Network",
          to: urls.devices.device.network({ id: systemId }),
        },
        {
          active: pathname.startsWith(
            urls.devices.device.configuration({ id: systemId })
          ),
          component: Link,
          label: "Configuration",
          to: urls.devices.device.configuration({ id: systemId }),
        },
      ]}
      title={
        <DeviceName
          data-testid="DeviceName"
          editingName={editingName}
          id={systemId}
          setEditingName={setEditingName}
        />
      }
    />
  );
};

export default DeviceDetailsHeader;
