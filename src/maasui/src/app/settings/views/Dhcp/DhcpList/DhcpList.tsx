import { useEffect, useState } from "react";

import {
  ContentSection,
  GenericTable,
  MainToolbar,
} from "@canonical/maas-react-components";
import {
  Button,
  Spinner,
  Link as VanillaLink,
} from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import useDHCPListColumns from "./useDHCPListColumns/useDHCPListColumns";

import SearchBox from "@/app/base/components/SearchBox";
import docsUrls from "@/app/base/docsUrls";
import { useWindowTitle } from "@/app/base/hooks";
import usePagination from "@/app/base/hooks/usePagination/usePagination";
import { useSidePanel } from "@/app/base/side-panel-context";
import DhcpAdd from "@/app/settings/views/Dhcp/DhcpAdd";
import { controllerActions } from "@/app/store/controller";
import { deviceActions } from "@/app/store/device";
import { dhcpsnippetActions } from "@/app/store/dhcpsnippet";
import dhcpsnippetSelectors from "@/app/store/dhcpsnippet/selectors";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";

const DhcpList = (): React.ReactElement => {
  const { openSidePanel } = useSidePanel();
  const [searchText, setSearchText] = useState("");

  const dhcpsnippetLoading = useSelector(dhcpsnippetSelectors.loading);
  const dhcpsnippetLoaded = useSelector(dhcpsnippetSelectors.loaded);
  const dhcpsnippets = useSelector((state: RootState) =>
    dhcpsnippetSelectors.search(state, searchText)
  );
  const { page, size, handlePageSizeChange, setPage } = usePagination(50);
  const columns = useDHCPListColumns();

  const dispatch = useDispatch();

  useWindowTitle("DHCP snippets");

  useEffect(() => {
    dispatch(dhcpsnippetActions.fetch());
    // The following models are used in DhcpTarget, but they are requested here
    // to prevent every DhcpTarget having to dispatch the actions.
    dispatch(subnetActions.fetch());
    dispatch(controllerActions.fetch());
    dispatch(deviceActions.fetch());
  }, [dispatch]);

  return (
    <ContentSection>
      <ContentSection.Content>
        <div className="settings-table">
          <MainToolbar>
            <MainToolbar.Title>DHCP snippets</MainToolbar.Title>
            <MainToolbar.Controls>
              <SearchBox
                onChange={setSearchText}
                placeholder="Search DHCP snippets"
                value={searchText}
              />
              <Button
                onClick={() => {
                  openSidePanel({
                    component: DhcpAdd,
                    title: "Add DHCP snippet",
                  });
                }}
              >
                Add snippet
              </Button>
            </MainToolbar.Controls>
          </MainToolbar>
          {dhcpsnippetLoading && (
            <div className="settings-table__loader">
              <Spinner />
            </div>
          )}
          <GenericTable
            aria-label="DHCP snippets"
            className="dhcp-snippets-list"
            columns={columns}
            data={dhcpsnippets.slice(size * (page - 1), size * page)}
            isLoading={dhcpsnippetLoading}
            noData="No DHCP snippets available."
            pagination={{
              currentPage: page,
              dataContext: "dhcp snippets",
              handlePageSizeChange: handlePageSizeChange,
              isPending: false,
              itemsPerPage: size,
              setCurrentPage: setPage,
              totalItems: dhcpsnippets.length,
            }}
            sorting={[{ id: "name", desc: false }]}
            variant="full-height"
          />
          {dhcpsnippetLoading && !dhcpsnippetLoaded && (
            <div className="settings-table__lines"></div>
          )}
          <p className="u-no-margin--bottom settings-table__help">
            <VanillaLink
              href={docsUrls.dhcp}
              rel="noopener noreferrer"
              target="_blank"
            >
              About DHCP
            </VanillaLink>
          </p>
        </div>
      </ContentSection.Content>
    </ContentSection>
  );
};

export default DhcpList;
