import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { Button } from "@canonical/react-components";
import { useSelector } from "react-redux";

import AddStaticRouteForm from "./AddStaticRouteForm";
import useStaticRoutesColumns from "./useStaticRoutesColumns/useStaticRoutesColumns";

import { useGetIsSuperUser } from "@/app/api/query/auth";
import TitledSection from "@/app/base/components/TitledSection";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { staticRouteActions } from "@/app/store/staticroute";
import staticRouteSelectors from "@/app/store/staticroute/selectors";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";

export type StaticRoutesProps = {
  subnetId: Subnet[SubnetMeta.PK];
};

export enum Labels {
  GatewayIp = "Gateway IP",
  Destination = "Destination",
  Metric = "Metric",
  Actions = "Actions",
}

const StaticRoutes = ({ subnetId }: StaticRoutesProps): ReactElement | null => {
  const { openSidePanel, isOpen } = useSidePanel();
  const staticRoutesLoading = useSelector(staticRouteSelectors.loading);
  const staticRoutes = useSelector(staticRouteSelectors.all).filter(
    (staticRoute) => staticRoute.source === subnetId
  );
  const subnetsLoading = useSelector(subnetSelectors.loading);
  const isSuperUser = useGetIsSuperUser();

  useFetchActions([staticRouteActions.fetch, subnetActions.fetch]);

  const columns = useStaticRoutesColumns();

  return (
    <TitledSection
      buttons={
        isSuperUser.data ? (
          <Button
            disabled={isOpen}
            onClick={() => {
              openSidePanel({
                component: AddStaticRouteForm,
                title: "Add static route",
                props: {
                  subnetId,
                },
              });
            }}
          >
            Add static route
          </Button>
        ) : null
      }
      className="u-no-padding--top"
      title="Static routes"
    >
      <GenericTable
        className="static-routes-table p-table-expanding--light"
        columns={columns}
        data={staticRoutes}
        isLoading={staticRoutesLoading || subnetsLoading}
        noData="No static routes for this subnet."
        sorting={[{ id: "gateway_ip", desc: false }]}
      />
    </TitledSection>
  );
};

export default StaticRoutes;
