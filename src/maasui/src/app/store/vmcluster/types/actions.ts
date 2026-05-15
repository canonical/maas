import type { VMCluster } from "./base";
import type { VMClusterMeta } from "./enum";

export type DeleteParams = {
  decompose?: boolean;
  id: VMCluster[VMClusterMeta.PK];
};
