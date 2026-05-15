import type { ReactElement } from "react";

import { MainToolbar } from "@canonical/maas-react-components";
import { Button } from "@canonical/react-components";

import { useNetworkDiscoveries } from "@/app/api/query/networkDiscovery";
import { useSidePanel } from "@/app/base/side-panel-context";
import { ClearAllForm } from "@/app/networkDiscovery/components";

export enum Labels {
  ClearAll = "Clear all discoveries",
}

const NetworkDiscoveryHeader = (): ReactElement => {
  const { openSidePanel } = useSidePanel();
  const discoveries = useNetworkDiscoveries();

  return (
    <MainToolbar>
      <MainToolbar.Title>Network discovery</MainToolbar.Title>
      <MainToolbar.Controls>
        <Button
          appearance="negative"
          data-testid="clear-all"
          disabled={discoveries.data?.total === 0}
          key="clear-all"
          onClick={() => {
            openSidePanel({
              component: ClearAllForm,
              title: "Clear all discoveries",
            });
          }}
        >
          {Labels.ClearAll}
        </Button>
      </MainToolbar.Controls>
    </MainToolbar>
  );
};

export default NetworkDiscoveryHeader;
