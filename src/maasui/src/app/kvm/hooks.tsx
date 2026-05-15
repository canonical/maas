import { useEffect } from "react";

import { useDispatch, useSelector } from "react-redux";
import { useLocation } from "react-router";

import urls from "@/app/base/urls";
import { podActions } from "@/app/store/pod";
import { PodType } from "@/app/store/pod/constants";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import { isId } from "@/app/utils";

/**
 * Handle setting a pod as active while a component is mounted.
 * @param id - The id of the pod to handle active state.
 */
export const useActivePod = (id: Pod["id"] | null): void => {
  const dispatch = useDispatch();

  useEffect(() => {
    if (id || id === 0) {
      dispatch(podActions.get(id));
      // Set pod as active to ensure all pod data is sent from the server.
      dispatch(podActions.setActive(id));
    }

    // Unset active pod on cleanup.
    return () => {
      dispatch(podActions.setActive(null));
    };
  }, [dispatch, id]);
};

/**
 * Handle redirects for the different types of KVM host at certain URLs.
 * @param id - The id of the KVM host to handle redirects for.
 */
export const useKVMDetailsRedirect = (id?: Pod["id"] | null): string | null => {
  const dispatch = useDispatch();
  const { pathname } = useLocation();
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, id)
  );
  const podsLoaded = useSelector(podSelectors.loaded);
  const clusterId = pod?.cluster ?? null;

  useEffect(() => {
    dispatch(podActions.fetch());
  }, [dispatch, id]);

  if (!isId(id) || !podsLoaded || !pod) {
    return null;
  }

  const isLXDClusterHost = clusterId !== null && pod.type === PodType.LXD;
  const isLXDSingleHost = clusterId === null && pod.type === PodType.LXD;
  const isVirshHost = pod.type === PodType.VIRSH;
  const clusterURLs = urls.kvm.lxd.cluster;
  const singleURLs = urls.kvm.lxd.single;
  const virshURLs = urls.kvm.virsh.details;

  if (isLXDClusterHost) {
    const hostId = pod.id;
    if (pathname.startsWith(singleURLs.vms({ id }))) {
      return clusterURLs.vms.host({ clusterId, hostId });
    } else if (
      pathname.startsWith(singleURLs.edit({ id })) ||
      pathname.startsWith(virshURLs.edit({ id }))
    ) {
      return clusterURLs.host.edit({ clusterId, hostId });
    } else if (!pathname.startsWith(clusterURLs.index({ clusterId }))) {
      return clusterURLs.vms.host({ clusterId, hostId });
    }
  }
  if (isLXDSingleHost && !pathname.startsWith(singleURLs.index({ id }))) {
    return singleURLs.index({ id });
  }
  if (isVirshHost && !pathname.startsWith(virshURLs.index({ id }))) {
    return virshURLs.index({ id });
  }

  return null;
};
