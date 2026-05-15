import type { ReactElement, ReactNode } from "react";
import { useEffect } from "react";

import { Col, Row, Spinner, Strip } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { useLocation, useNavigate } from "react-router";

import KVMListHeader from "./KVMListHeader";
import LXDHostsTable from "./LXDHostsTable";
import VirshTable from "./components/VirshTable/VirshTable";

import PageContent from "@/app/base/components/PageContent/PageContent";
import { useFetchActions, useWindowTitle } from "@/app/base/hooks";
import type { SyncNavigateFunction } from "@/app/base/types";
import urls from "@/app/base/urls";
import { podActions } from "@/app/store/pod";
import podSelectors from "@/app/store/pod/selectors";
import { vmClusterActions } from "@/app/store/vmcluster";
import vmclusterSelectors from "@/app/store/vmcluster/selectors";

export enum Label {
  Title = "KVM list",
}

const KVMList = (): ReactElement => {
  const navigate: SyncNavigateFunction = useNavigate();
  const location = useLocation();
  const podsLoading = useSelector(podSelectors.loading);
  const lxdKvms = useSelector(podSelectors.lxd);
  const virshKvms = useSelector(podSelectors.virsh);
  const vmclusters = useSelector(vmclusterSelectors.all);
  const vmclustersLoading = useSelector(vmclusterSelectors.loading);
  const hasLXDs = vmclusters.length + lxdKvms.length > 0;
  const hasVirsh = virshKvms.length > 0;
  const showingLXD = location.pathname.endsWith(urls.kvm.lxd.index);
  const showingVirsh = location.pathname.endsWith(urls.kvm.virsh.index);
  const title = showingLXD ? "LXD" : showingVirsh ? "Virsh" : "KVM";
  useWindowTitle(title);

  useFetchActions([podActions.fetch, vmClusterActions.fetch]);

  // Redirect to the appropriate tab when arriving at /kvm.
  useEffect(() => {
    if (!showingLXD && !showingVirsh) {
      navigate(urls.kvm.lxd.index, { replace: true });
    }
  }, [navigate, showingLXD, showingVirsh]);

  let content: ReactNode;
  if (podsLoading || vmclustersLoading) {
    content = <Spinner text="Loading..." />;
  } else if (showingLXD && hasLXDs) {
    content = (
      <Strip className="u-no-padding--bottom" data-testid="lxd-table" shallow>
        <LXDHostsTable />
      </Strip>
    );
  } else if (showingVirsh && hasVirsh) {
    content = (
      <Strip data-testid="virsh-table" shallow>
        <VirshTable />
      </Strip>
    );
  } else {
    const hostType = showingLXD ? "LXD" : "Virsh";
    content = (
      <Strip data-testid="no-hosts" deep>
        <Row>
          <Col className="u-flex" emptyLarge={4} size={6}>
            <div className="">
              <h4>No {hostType} hosts available</h4>
              <p>
                Select the Add {hostType} host button and add the {hostType}{" "}
                host to see hosts on this page.
              </p>
            </div>
          </Col>
        </Row>
      </Strip>
    );
  }
  return (
    <PageContent
      aria-label={Label.Title}
      header={<KVMListHeader title={title} />}
    >
      {content}
    </PageContent>
  );
};

export default KVMList;
