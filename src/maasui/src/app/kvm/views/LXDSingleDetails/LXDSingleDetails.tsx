import type { ReactElement } from "react";
import { useCallback, useEffect, useState } from "react";

import { useSelector } from "react-redux";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router";

import LXDSingleDetailsHeader from "./LXDSingleDetailsHeader";
import LXDSingleResources from "./LXDSingleResources";
import LXDSingleSettings from "./LXDSingleSettings";
import LXDSingleVMs from "./LXDSingleVMs";

import ModelNotFound from "@/app/base/components/ModelNotFound";
import PageContent from "@/app/base/components/PageContent/PageContent";
import { useGetURLId } from "@/app/base/hooks/urls";
import type { SetSearchFilter, SyncNavigateFunction } from "@/app/base/types";
import urls from "@/app/base/urls";
import { useActivePod, useKVMDetailsRedirect } from "@/app/kvm/hooks";
import { FilterMachines } from "@/app/store/machine/utils";
import podSelectors from "@/app/store/pod/selectors";
import { PodMeta } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import { isId, getRelativeRoute } from "@/app/utils";

export enum Label {
  Title = "LXD details",
}

const LXDSingleDetails = (): ReactElement => {
  const navigate: SyncNavigateFunction = useNavigate();
  const location = useLocation();
  const id = useGetURLId(PodMeta.PK);
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, id)
  );
  const loading = useSelector(podSelectors.loading);
  // Search filter is determined by the URL and used to initialise state.
  const currentFilters = FilterMachines.queryStringToFilters(location.search);
  const [searchFilter, setFilter] = useState<string>(
    FilterMachines.filtersToString(currentFilters)
  );
  useActivePod(id);
  const redirectURL = useKVMDetailsRedirect(id);

  const setSearchFilter: SetSearchFilter = useCallback(
    (searchFilter: string) => {
      setFilter(searchFilter);
      const filters = FilterMachines.getCurrentFilters(searchFilter);
      navigate({ search: FilterMachines.filtersToQueryString(filters) });
    },
    [setFilter, navigate]
  );

  useEffect(() => {
    if (redirectURL) {
      navigate(redirectURL, { replace: true });
    }
  }, [navigate, redirectURL]);

  if (!isId(id) || (!loading && !pod)) {
    return (
      <ModelNotFound
        id={id}
        linkURL={urls.kvm.lxd.index}
        modelName="LXD host"
      />
    );
  }
  const base = urls.kvm.lxd.single.index(null);
  return (
    <PageContent
      aria-label={Label.Title}
      header={<LXDSingleDetailsHeader id={id} />}
    >
      {pod && (
        <Routes>
          <Route
            element={
              <LXDSingleVMs
                id={id}
                searchFilter={searchFilter}
                setSearchFilter={setSearchFilter}
              />
            }
            path={getRelativeRoute(urls.kvm.lxd.single.vms(null), base)}
          />
          <Route
            element={<LXDSingleResources id={id} />}
            path={getRelativeRoute(urls.kvm.lxd.single.resources(null), base)}
          />
          <Route
            element={<LXDSingleSettings id={id} />}
            path={getRelativeRoute(urls.kvm.lxd.single.edit(null), base)}
          />
          <Route
            element={<Navigate replace to={urls.kvm.lxd.single.vms({ id })} />}
            path="/"
          />
        </Routes>
      )}
    </PageContent>
  );
};

export default LXDSingleDetails;
