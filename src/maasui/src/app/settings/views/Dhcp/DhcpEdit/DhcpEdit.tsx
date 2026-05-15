import type { ReactElement } from "react";

import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import DhcpForm from "../DhcpForm";

import { useFetchActions } from "@/app/base/hooks";
import { dhcpsnippetActions } from "@/app/store/dhcpsnippet";
import dhcpsnippetSelectors from "@/app/store/dhcpsnippet/selectors";
import type { DHCPSnippet } from "@/app/store/dhcpsnippet/types";
import type { RootState } from "@/app/store/root/types";

type DhcpEditProps = {
  id: DHCPSnippet["id"];
};

export const DhcpEdit = ({ id }: DhcpEditProps): ReactElement => {
  const loading = useSelector(dhcpsnippetSelectors.loading);
  const dhcpsnippet = useSelector((state: RootState) =>
    dhcpsnippetSelectors.getById(state, id)
  );

  useFetchActions([dhcpsnippetActions.fetch]);

  if (loading) {
    return <Spinner text="Loading..." />;
  }
  if (!dhcpsnippet) {
    return <h4>DHCP snippet not found</h4>;
  }
  return <DhcpForm dhcpSnippet={dhcpsnippet} />;
};

export default DhcpEdit;
