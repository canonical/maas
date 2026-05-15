import type { ReactElement } from "react";

import { Button } from "@canonical/react-components";

import { useGetIsSuperUser } from "@/app/api/query/auth";
import SectionHeader from "@/app/base/components/SectionHeader";
import { useSidePanel } from "@/app/base/side-panel-context";
import { DeleteFabric } from "@/app/networks/views/Fabrics/components";
import type { Fabric } from "@/app/store/fabric/types";

type FabricDetailsHeaderProps = {
  fabric: Fabric | null;
};

const FabricDetailsHeader = ({
  fabric,
}: FabricDetailsHeaderProps): ReactElement => {
  const { openSidePanel } = useSidePanel();
  const isSuperUser = useGetIsSuperUser();

  return (
    <SectionHeader
      buttons={
        isSuperUser.data
          ? [
              <Button
                appearance="neutral"
                onClick={() => {
                  openSidePanel({
                    component: DeleteFabric,
                    title: "Delete fabric",
                    props: { id: fabric?.id },
                  });
                }}
              >
                Delete fabric
              </Button>,
            ]
          : null
      }
      loading={!fabric}
      title={fabric?.name}
    />
  );
};

export default FabricDetailsHeader;
