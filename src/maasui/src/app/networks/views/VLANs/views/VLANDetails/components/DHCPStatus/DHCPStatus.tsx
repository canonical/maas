import { ExternalLink } from "@canonical/maas-react-components";
import {
  Button,
  Col,
  Notification as NotificationBanner,
  Row,
  Spinner,
} from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import ConfigureDHCP from "../ConfigureDHCP";

import ControllerLink from "@/app/base/components/ControllerLink";
import Definition from "@/app/base/components/Definition";
import TitledSection from "@/app/base/components/TitledSection";
import docsUrls from "@/app/base/docsUrls";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { Fabric } from "@/app/store/fabric/types";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";
import { getFullVLANName } from "@/app/store/vlan/utils";
import { isId } from "@/app/utils";

type Props = {
  id: VLAN[VLANMeta.PK] | null;
};

// Note this is not the same as the getDHCPStatus VLAN util as it uses slightly
// different language and renders a link for the relayed VLAN.
const getDHCPStatus = (vlan: VLAN, vlans: VLAN[], fabrics: Fabric[]) => {
  if (vlan.dhcp_on) {
    return "Enabled";
  }
  if (vlan.external_dhcp) {
    return `External (${vlan.external_dhcp})`;
  }
  if (isId(vlan.relay_vlan)) {
    return (
      <span>
        Relayed via{" "}
        <Link to={urls.networks.vlan.index({ id: vlan.relay_vlan })}>
          {getFullVLANName(vlan.relay_vlan, vlans, fabrics)}
        </Link>
      </span>
    );
  }
  return "Disabled";
};

const DHCPStatus = ({ id }: Props): React.ReactElement | null => {
  const { openSidePanel } = useSidePanel();
  const fabrics = useSelector(fabricSelectors.all);
  const fabricsLoading = useSelector(fabricSelectors.loading);
  const vlans = useSelector(vlanSelectors.all);
  const vlansLoading = useSelector(vlanSelectors.loading);
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, id)
  );
  const vlanSubnets = useSelector((state: RootState) =>
    subnetSelectors.getByIds(state, vlan?.subnet_ids || null)
  );
  const subnetsLoading = useSelector(subnetSelectors.loading);

  useFetchActions([
    fabricActions.fetch,
    subnetActions.fetch,
    vlanActions.fetch,
  ]);

  if (!vlan || fabricsLoading || subnetsLoading || vlansLoading) {
    return (
      <TitledSection data-testid="loading-data" title="DHCP">
        <p>
          <Spinner text="Loading" />
        </p>
      </TitledSection>
    );
  }

  const hasVLANSubnets = vlanSubnets.length > 0;
  const hasOwnDHCP =
    (vlan.dhcp_on || vlan.external_dhcp) &&
    (!!vlan.primary_rack || !!vlan.secondary_rack);
  const hasHighAvailability = !!vlan.primary_rack && !!vlan.secondary_rack;
  return (
    <TitledSection
      buttons={
        <Button
          disabled={!hasVLANSubnets}
          onClick={() => {
            openSidePanel({
              component: ConfigureDHCP,
              title: "Configure DHCP",
              size: "large",
              props: {
                vlan,
              },
            });
          }}
        >
          Configure DHCP
        </Button>
      }
      title="DHCP"
    >
      {!hasVLANSubnets && (
        <NotificationBanner severity="caution">
          No subnets are available on this VLAN. DHCP cannot be enabled.
        </NotificationBanner>
      )}
      <Row>
        <Col size={6}>
          <Definition label="Status">
            <span data-testid="dhcp-status">
              {getDHCPStatus(vlan, vlans, fabrics)}
            </span>
          </Definition>
          {hasOwnDHCP && (
            <Definition label="High availability">
              <span data-testid="high-availability">
                {hasHighAvailability ? "Yes" : "No"}
              </span>
            </Definition>
          )}
        </Col>
        <Col size={6}>
          {hasOwnDHCP && (
            <>
              {hasHighAvailability ? (
                <>
                  <Definition label="Primary rack">
                    <ControllerLink systemId={vlan.primary_rack} />
                  </Definition>
                  <Definition label="Secondary rack">
                    <ControllerLink systemId={vlan.secondary_rack} />
                  </Definition>
                </>
              ) : (
                <Definition label="Rack controller">
                  <ControllerLink
                    systemId={vlan.primary_rack || vlan.secondary_rack}
                  />
                </Definition>
              )}
            </>
          )}
        </Col>
      </Row>
      <p>
        <ExternalLink to={docsUrls.dhcp}>About DHCP</ExternalLink>
      </p>
    </TitledSection>
  );
};

export default DHCPStatus;
