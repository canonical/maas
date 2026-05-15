import type { ReactElement } from "react";

import { MainToolbar } from "@canonical/maas-react-components";
import { Button, Spinner } from "@canonical/react-components";

import ZonesListTitle from "./ZonesListTitle";

import { useZoneCount } from "@/app/api/query/zones";
import ModelListSubtitle from "@/app/base/components/ModelListSubtitle";
import { useSidePanel } from "@/app/base/side-panel-context";
import { AddZone } from "@/app/zones/components";

const ZonesListHeader = (): ReactElement => {
  const { openSidePanel } = useSidePanel();
  const zonesCount = useZoneCount();

  return (
    <MainToolbar>
      <MainToolbar.Title>
        <ZonesListTitle />
      </MainToolbar.Title>
      {zonesCount.isSuccess ? (
        <ModelListSubtitle available={zonesCount.data} modelName="AZ" />
      ) : (
        <Spinner text="Loading..." />
      )}
      <MainToolbar.Controls>
        <Button
          data-testid="add-zone"
          key="add-zone"
          onClick={() => {
            openSidePanel({ component: AddZone, title: "Add AZ" });
          }}
        >
          Add AZ
        </Button>
      </MainToolbar.Controls>
    </MainToolbar>
  );
};

export default ZonesListHeader;
