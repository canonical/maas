import { useState } from "react";

import { GenericTable, MainToolbar } from "@canonical/maas-react-components";
import { Button, Tooltip } from "@canonical/react-components";
import { useSelector } from "react-redux";

import SearchBox from "@/app/base/components/SearchBox";
import { useFetchActions, useWindowTitle } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { LicenseKeyAdd } from "@/app/settings/views/LicenseKeys/components";
import useLicenseKeyTableColumns from "@/app/settings/views/LicenseKeys/components/LicenseKeyTable/useLicenseKeyTableColumns/useLicenseKeyTableColumns";
import { generalActions } from "@/app/store/general";
import { osInfo as osInfoSelectors } from "@/app/store/general/selectors";
import { licenseKeysActions } from "@/app/store/licensekeys";
import licenseKeysSelectors from "@/app/store/licensekeys/selectors";
import type { RootState } from "@/app/store/root/types";

const LicenseKeyTable = () => {
  const { openSidePanel } = useSidePanel();
  const [searchText, setSearchText] = useState("");

  const licenseKeysLoading = useSelector(licenseKeysSelectors.loading);
  const osystems = useSelector(osInfoSelectors.getLicensedOsystems);

  const licenseKeys = useSelector((state: RootState) =>
    licenseKeysSelectors.search(state, searchText)
  );

  useWindowTitle("License keys");

  useFetchActions([licenseKeysActions.fetch, generalActions.fetchOsInfo]);

  const addBtnDisabled = osystems.length === 0;
  const tooltip = addBtnDisabled
    ? "No available licensed operating systems."
    : null;

  const columns = useLicenseKeyTableColumns();

  return (
    <div className="license-key-list">
      <MainToolbar>
        <MainToolbar.Title>License keys</MainToolbar.Title>
        <MainToolbar.Controls>
          <SearchBox
            onChange={setSearchText}
            placeholder="Search license keys"
            value={searchText}
          />
          <Tooltip message={tooltip} position="left">
            <Button
              disabled={addBtnDisabled}
              onClick={() => {
                openSidePanel({
                  component: LicenseKeyAdd,
                  title: "Add license key",
                });
              }}
            >
              Add license key
            </Button>
          </Tooltip>
        </MainToolbar.Controls>
      </MainToolbar>
      <GenericTable
        columns={columns}
        data={licenseKeys ?? []}
        isLoading={licenseKeysLoading}
        noData="No license keys available."
      />
    </div>
  );
};

export default LicenseKeyTable;
