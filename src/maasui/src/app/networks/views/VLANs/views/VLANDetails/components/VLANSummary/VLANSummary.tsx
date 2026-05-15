import { Button, Col, Row } from "@canonical/react-components";
import { useSelector } from "react-redux";

import { useGetIsSuperUser } from "@/app/api/query/auth";
import Definition from "@/app/base/components/Definition";
import FabricLink from "@/app/base/components/FabricLink";
import SpaceLink from "@/app/base/components/SpaceLink";
import TitledSection from "@/app/base/components/TitledSection";
import { useSidePanel } from "@/app/base/side-panel-context";
import {
  EditVLAN,
  VLANControllers,
} from "@/app/networks/views/VLANs/components";
import type { RootState } from "@/app/store/root/types";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";

type Props = {
  id: VLAN[VLANMeta.PK] | null;
};

const VLANSummary = ({ id }: Props): React.ReactElement | null => {
  const { openSidePanel } = useSidePanel();
  const isSuperUser = useGetIsSuperUser();
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, id)
  );

  if (!id || !vlan) {
    return null;
  }

  return (
    <TitledSection
      buttons={
        isSuperUser.data && (
          <Button
            onClick={() => {
              openSidePanel({
                component: EditVLAN,
                title: "Edit VLAN",
                props: { id },
              });
            }}
          >
            Edit
          </Button>
        )
      }
      title="VLAN summary"
    >
      <Row>
        <Col size={6}>
          <Definition description={`${vlan.vid}`} label="VID" />
          <Definition description={vlan.name} label="Name" />
          <Definition description={`${vlan.mtu}`} label="MTU" />
          <Definition description={vlan.description} label="Description" />
        </Col>
        <Col size={6}>
          <Definition label="Space">
            <SpaceLink id={vlan.space} />
          </Definition>
          <Definition label="Fabric">
            <FabricLink id={vlan.fabric} />
          </Definition>
          <VLANControllers id={id} />
        </Col>
      </Row>
    </TitledSection>
  );
};

export default VLANSummary;
