import type { ReactElement } from "react";
import { useEffect } from "react";

import { useSelector } from "react-redux";
import { Navigate, Route, Routes, useNavigate } from "react-router";

import VirshDetailsHeader from "./VirshDetailsHeader";
import VirshResources from "./VirshResources";
import VirshSettings from "./VirshSettings";

import ModelNotFound from "@/app/base/components/ModelNotFound";
import PageContent from "@/app/base/components/PageContent/PageContent";
import { useGetURLId } from "@/app/base/hooks/urls";
import type { SyncNavigateFunction } from "@/app/base/types";
import urls from "@/app/base/urls";
import { useActivePod, useKVMDetailsRedirect } from "@/app/kvm/hooks";
import podSelectors from "@/app/store/pod/selectors";
import { PodMeta } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import { isId, getRelativeRoute } from "@/app/utils";

export enum Label {
  Title = "Virsh details",
}

const VirshDetails = (): ReactElement => {
  const navigate: SyncNavigateFunction = useNavigate();
  const id = useGetURLId(PodMeta.PK);

  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, id)
  );
  const loading = useSelector(podSelectors.loading);

  useActivePod(id);
  const redirectURL = useKVMDetailsRedirect(id);

  useEffect(() => {
    if (redirectURL) {
      navigate(redirectURL, { replace: true });
    }
  }, [navigate, redirectURL]);

  if (!isId(id) || (!loading && !pod)) {
    return (
      <ModelNotFound
        id={id}
        linkURL={urls.kvm.virsh.index}
        modelName="Virsh host"
      />
    );
  }
  const base = urls.kvm.virsh.details.index(null);
  return (
    <PageContent
      aria-label={Label.Title}
      header={<VirshDetailsHeader id={id} />}
    >
      {pod && (
        <Routes>
          <Route
            element={<VirshResources id={id} />}
            path={getRelativeRoute(
              urls.kvm.virsh.details.resources(null),
              base
            )}
          />
          <Route
            element={<VirshSettings id={id} />}
            path={getRelativeRoute(urls.kvm.virsh.details.edit(null), base)}
          />
          <Route
            element={
              <Navigate replace to={urls.kvm.virsh.details.resources({ id })} />
            }
            path="/"
          />
        </Routes>
      )}
    </PageContent>
  );
};

export default VirshDetails;
