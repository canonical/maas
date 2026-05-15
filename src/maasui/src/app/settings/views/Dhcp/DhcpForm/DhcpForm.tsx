import { useState } from "react";

import BaseDhcpForm from "@/app/base/components/DhcpForm";
import type { DHCPFormValues } from "@/app/base/components/DhcpForm/types";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { DHCPSnippet } from "@/app/store/dhcpsnippet/types";

type Props = {
  dhcpSnippet?: DHCPSnippet;
};

export const DhcpForm = ({ dhcpSnippet }: Props): React.ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const [name, setName] = useState<DHCPFormValues["name"]>();
  const editing = !!dhcpSnippet;
  const title = editing ? `Editing \`${name}\`` : "Add DHCP snippet";

  return (
    <BaseDhcpForm
      analyticsCategory="DHCP snippet settings"
      aria-label={title}
      id={dhcpSnippet?.id}
      onCancel={closeSidePanel}
      onSave={closeSidePanel}
      onValuesChanged={(values) => {
        setName(values.name);
      }}
    />
  );
};

export default DhcpForm;
