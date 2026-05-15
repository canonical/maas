import { Col, Row } from "@canonical/react-components";
import { useSelector } from "react-redux";

import SubnetSummaryForm from "./SubnetSummaryForm";
import ActiveDiscoveryLabel from "./components/ActiveDiscoveryLabel";
import AllowDNSResolutionLabel from "./components/AllowDNSResolutionLabel";
import ManagedAllocationLabel from "./components/ManagedAllocationLabel";
import ProxyAccessLabel from "./components/ProxyAccessLabel";
import SubnetSpace from "./components/SubnetSpace";

import Definition from "@/app/base/components/Definition";
import EditableSection from "@/app/base/components/EditableSection";
import FabricLink from "@/app/base/components/FabricLink";
import VLANLink from "@/app/base/components/VLANLink";
import { useFetchActions } from "@/app/base/hooks";
import { fabricActions } from "@/app/store/fabric";
import type { RootState } from "@/app/store/root/types";
import { spaceActions } from "@/app/store/space";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";

type Props = {
  id: Subnet[SubnetMeta.PK] | null;
};

const SubnetSummary = ({ id }: Props): React.ReactElement | null => {
  const subnet = useSelector((state: RootState) =>
    subnetSelectors.getById(state, id)
  );
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, subnet?.vlan)
  );

  useFetchActions([spaceActions.fetch, vlanActions.fetch, fabricActions.fetch]);

  if (!subnet) {
    return null;
  }

  return (
    <EditableSection
      className="u-no-padding--top"
      renderContent={(editing, setEditing) =>
        editing ? (
          <SubnetSummaryForm
            handleDismiss={() => {
              setEditing(false);
            }}
            id={subnet.id}
          />
        ) : (
          <Row>
            <Col size={6}>
              <Definition description={subnet.name} label="Name" />
              <Definition description={subnet.cidr} label="CIDR" />
              <Definition label="Gateway IP">{subnet.gateway_ip}</Definition>
              <Definition description={subnet.dns_servers} label="DNS" />
              <Definition
                description={subnet.description}
                label="Description"
              />
              <Definition label={<ManagedAllocationLabel />}>
                {subnet.managed ? "Enabled" : "Disabled"}
              </Definition>
            </Col>
            <Col size={6}>
              <Definition label={<ActiveDiscoveryLabel />}>
                {subnet.active_discovery ? "Enabled" : "Disabled"}
              </Definition>
              <Definition
                label={<ProxyAccessLabel allowProxy={subnet.allow_proxy} />}
              >
                {subnet.allow_proxy ? "Allowed" : "Disallowed"}
              </Definition>
              <Definition
                label={<AllowDNSResolutionLabel allowDNS={subnet.allow_dns} />}
              >
                {subnet.allow_dns ? "Allowed" : "Disallowed"}
              </Definition>
              <Definition label="Fabric">
                <FabricLink id={vlan?.fabric} />
              </Definition>
              <Definition label="VLAN">
                <VLANLink id={subnet.vlan} />
              </Definition>
              <SubnetSpace spaceId={subnet.space} />
            </Col>
          </Row>
        )
      }
      title="Subnet summary"
    />
  );
};

export default SubnetSummary;
