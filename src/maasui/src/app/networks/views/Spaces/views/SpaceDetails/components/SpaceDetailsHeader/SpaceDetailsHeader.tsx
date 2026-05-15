import type { ReactElement } from "react";

import { Button } from "@canonical/react-components";

import SectionHeader from "@/app/base/components/SectionHeader";
import { useSidePanel } from "@/app/base/side-panel-context";
import { DeleteSpace } from "@/app/networks/views/Spaces/components";
import type { Space } from "@/app/store/space/types";

type SpaceDetailsHeaderProps = {
  space: Space | null;
};

const SpaceDetailsHeader = ({
  space,
}: SpaceDetailsHeaderProps): ReactElement => {
  const { openSidePanel, isOpen } = useSidePanel();
  return (
    <SectionHeader
      buttons={[
        <Button
          disabled={isOpen || !space}
          onClick={() => {
            openSidePanel({
              component: DeleteSpace,
              title: "Delete space",
              props: { id: space!.id },
            });
          }}
        >
          Delete space
        </Button>,
      ]}
      loading={!space}
      title={space?.name}
    />
  );
};

export default SpaceDetailsHeader;
