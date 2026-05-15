import type { BasePod } from "@/app/store/pod/types";
import type { VMCluster } from "@/app/store/vmcluster/types";
import { argPath } from "@/app/utils";

const withClusterId = argPath<{ clusterId: VMCluster["id"] }>;
const withId = argPath<{ id: BasePod["id"] }>;
const withClusterIdHostId = argPath<{
  clusterId: VMCluster["id"];
  hostId: BasePod["id"];
}>;

const urls = {
  index: "/kvm",
  lxd: {
    index: "/kvm/lxd",
    cluster: {
      index: withClusterId("/kvm/lxd/cluster/:clusterId"),
      edit: withClusterId("/kvm/lxd/cluster/:clusterId/edit"),
      hosts: withClusterId("/kvm/lxd/cluster/:clusterId/hosts"),
      host: {
        index: withClusterIdHostId("/kvm/lxd/cluster/:clusterId/host/:hostId"),
        edit: withClusterIdHostId(
          "/kvm/lxd/cluster/:clusterId/host/:hostId/edit"
        ),
      },
      resources: withClusterId("/kvm/lxd/cluster/:clusterId/resources"),
      vms: {
        index: withClusterId("/kvm/lxd/cluster/:clusterId/vms"),
        host: withClusterIdHostId("/kvm/lxd/cluster/:clusterId/vms/:hostId"),
      },
    },
    single: {
      index: withId("/kvm/lxd/:id"),
      edit: withId("/kvm/lxd/:id/edit"),
      resources: withId("/kvm/lxd/:id/resources"),
      vms: withId("/kvm/lxd/:id/vms"),
    },
  },
  virsh: {
    index: "/kvm/virsh",
    details: {
      index: withId("/kvm/virsh/:id"),
      edit: withId("/kvm/virsh/:id/edit"),
      resources: withId("/kvm/virsh/:id/resources"),
    },
  },
} as const;

export default urls;
