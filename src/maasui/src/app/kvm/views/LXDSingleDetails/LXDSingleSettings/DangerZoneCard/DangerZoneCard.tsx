import type { ReactElement, ReactNode } from "react";

import { Button, Col, Row } from "@canonical/react-components";

import FormCard from "@/app/base/components/FormCard";
import { useSidePanel } from "@/app/base/side-panel-context";
import DeleteForm from "@/app/kvm/components/DeleteForm";
import type { Pod, PodMeta } from "@/app/store/pod/types";
import type { VMCluster, VMClusterMeta } from "@/app/store/vmcluster/types";

type Props = {
  clusterId?: VMCluster[VMClusterMeta.PK];
  hostId?: Pod[PodMeta.PK];
  message: ReactNode;
};

const DangerZoneCard = ({
  clusterId,
  hostId,
  message,
}: Props): ReactElement => {
  const { openSidePanel } = useSidePanel();

  return (
    <FormCard highlighted={false} sidebar={false} title="Danger zone">
      <Row>
        <Col size={5}>{message}</Col>
        <Col className="u-align--right u-vertically-center" size={5}>
          <Button
            className="u-no-margin--bottom"
            data-testid="remove-kvm"
            onClick={() => {
              openSidePanel({
                component: DeleteForm,
                title: "Delete KVM",
                props: { clusterId, hostId },
              });
            }}
          >
            {!!clusterId || clusterId === 0
              ? "Remove cluster"
              : "Remove KVM host"}
          </Button>
        </Col>
      </Row>
    </FormCard>
  );
};

export default DangerZoneCard;
