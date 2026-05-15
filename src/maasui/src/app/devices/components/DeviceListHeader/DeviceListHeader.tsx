import { type Dispatch, type SetStateAction, useEffect, useState } from "react";

import { MainToolbar } from "@canonical/maas-react-components";
import { Button, Col, Spinner } from "@canonical/react-components";
import type { RowSelectionState } from "@tanstack/react-table";
import { useSelector } from "react-redux";

import DeviceFilterAccordion from "./DeviceFilterAccordion";

import DebounceSearchBox from "@/app/base/components/DebounceSearchBox";
import ModelListSubtitle from "@/app/base/components/ModelListSubtitle";
import NodeActionMenu from "@/app/base/components/NodeActionMenu";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { SetSearchFilter } from "@/app/base/types";
import {
  AddDeviceForm,
  DeviceActionFormWrapper,
} from "@/app/devices/components";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device } from "@/app/store/device/types";
import { NodeActions } from "@/app/store/types/node";

type Props = {
  rowSelection: RowSelectionState;
  setRowSelection: Dispatch<SetStateAction<RowSelectionState>>;
  searchFilter: string;
  setSearchFilter: SetSearchFilter;
};

const DeviceListHeader = ({
  rowSelection,
  setRowSelection,
  searchFilter,
  setSearchFilter,
}: Props): React.ReactElement => {
  const devices = useSelector(deviceSelectors.all);
  const devicesLoaded = useSelector(deviceSelectors.loaded);
  const selectedDevices = devices.filter((device: Device) =>
    Object.keys(rowSelection).includes(device.id.toString())
  );
  const [searchText, setSearchText] = useState(searchFilter);
  const { openSidePanel } = useSidePanel();

  useEffect(() => {
    // If the filters change then update the search input text.
    setSearchText(searchFilter);
  }, [searchFilter]);

  return (
    <MainToolbar>
      <MainToolbar.Title data-testid="section-header-title">
        Devices
      </MainToolbar.Title>
      {devicesLoaded ? (
        <ModelListSubtitle
          available={devices.length}
          modelName="device"
          selected={selectedDevices.length}
        />
      ) : (
        <Spinner text="Loading" />
      )}
      <MainToolbar.Controls>
        <Col size={3}>
          <DeviceFilterAccordion
            searchText={searchText}
            setSearchText={setSearchFilter}
          />
        </Col>
        <DebounceSearchBox
          onDebounced={(debouncedText) => {
            setSearchFilter(debouncedText);
          }}
          searchText={searchText}
          setSearchText={setSearchText}
        />
        <Button
          data-testid="add-device-button"
          disabled={selectedDevices.length > 0}
          onClick={() => {
            openSidePanel({
              component: AddDeviceForm,
              title: "Add device",
              size: "regular",
            });
          }}
        >
          Add device
        </Button>
        <NodeActionMenu
          filterActions
          hasSelection={selectedDevices.length > 0}
          nodeDisplay="device"
          nodes={selectedDevices}
          onActionClick={(action) => {
            openSidePanel({
              component: DeviceActionFormWrapper,
              title: action === NodeActions.DELETE ? "Delete" : "Set zone",
              props: {
                action:
                  action === NodeActions.DELETE ? action : NodeActions.SET_ZONE,
                devices: selectedDevices,
                viewingDetails: false,
                setRowSelection,
              },
            });
          }}
          showCount
        />
      </MainToolbar.Controls>
    </MainToolbar>
  );
};

export default DeviceListHeader;
