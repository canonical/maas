import type { ReactElement } from "react";

import { useClearNetworkDiscoveries } from "@/app/api/query/networkDiscovery";
import type { DiscoveryResponse } from "@/app/apiclient";
import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type Props = {
  discovery: DiscoveryResponse;
};

const DiscoveryDeleteForm = ({ discovery }: Props): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const clearDiscovery = useClearNetworkDiscoveries();

  return (
    <ModelActionForm
      aria-label="Delete discovery"
      errors={clearDiscovery.error}
      initialValues={{}}
      message={`Are you sure you want to delete discovery "${
        discovery.hostname || "Unknown"
      }"?`}
      modelType="discovery"
      onCancel={closeSidePanel}
      onSubmit={() => {
        clearDiscovery.mutate({
          query: { ip: discovery.ip, mac: discovery.mac_address },
        });
      }}
      onSuccess={closeSidePanel}
      saved={clearDiscovery.isSuccess}
      saving={clearDiscovery.isPending}
    />
  );
};

export default DiscoveryDeleteForm;
