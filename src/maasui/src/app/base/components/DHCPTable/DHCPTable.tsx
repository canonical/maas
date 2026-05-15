import { ExternalLink, GenericTable } from "@canonical/maas-react-components";
import { List } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import TitledSection from "../TitledSection";

import useDHCPTableColumns from "./useDHCPTableColumns/useDHCPTableColumns";

import docsUrls from "@/app/base/docsUrls";
import { useFetchActions } from "@/app/base/hooks";
import settingsURLs from "@/app/settings/urls";
import { dhcpsnippetActions } from "@/app/store/dhcpsnippet";
import dhcpsnippetSelectors from "@/app/store/dhcpsnippet/selectors";
import type { IPRange } from "@/app/store/iprange/types";
import type { RootState } from "@/app/store/root/types";
import type { Subnet } from "@/app/store/subnet/types";
import type { Node } from "@/app/store/types/node";
import { generateEmptyStateMsg, getTableStatus } from "@/app/utils";

type BaseProps = {
  className?: string;
  modelName: string;
  node?: Node;
  subnets?: Subnet[];
  ipRanges?: IPRange[];
};

type NodeProps = BaseProps & {
  node: Node;
};

type SubnetProps = BaseProps & {
  subnets: Subnet[];
};

export type Props = NodeProps | SubnetProps;

export enum Labels {
  LoadingData = "Loading DHCP snippets",
  SectionTitle = "DHCP snippets",
}

export enum TestIds {
  AppliesTo = "snippet-applies-to",
}

const DHCPTable = ({
  className,
  node,
  subnets,
  ipRanges,
  modelName,
}: Props): React.ReactElement | null => {
  const dhcpsnippetLoading = useSelector(dhcpsnippetSelectors.loading);
  const subnetIds = subnets?.map(({ id }) => id) || null;
  const dhcpsnippets = useSelector((state: RootState) =>
    node
      ? dhcpsnippetSelectors.getByNode(state, node?.system_id)
      : dhcpsnippetSelectors.getBySubnets(state, subnetIds)
  );

  useFetchActions([dhcpsnippetActions.fetch]);
  const tableStatus = getTableStatus({ isLoading: dhcpsnippetLoading });

  const columns = useDHCPTableColumns({
    originalNode: node,
    subnets,
    ipranges: ipRanges,
  });

  return (
    <TitledSection className={className} title={Labels.SectionTitle}>
      {node || subnets?.length ? (
        <>
          <GenericTable
            aria-label="DHCP snippets"
            className="dhcp-snippets-table"
            columns={columns}
            data={dhcpsnippets}
            isLoading={dhcpsnippetLoading}
            noData={generateEmptyStateMsg(tableStatus, {
              default: `No DHCP snippets applied to this ${modelName}.`,
            })}
            variant="full-height"
          />
          <List
            items={[
              <Link to={settingsURLs.dhcp.index}>
                All snippets: Settings &gt; DHCP snippets
              </Link>,
              <ExternalLink to={docsUrls.dhcp}>
                About DHCP snippets
              </ExternalLink>,
            ]}
            middot
          />
        </>
      ) : null}
    </TitledSection>
  );
};

export default DHCPTable;
