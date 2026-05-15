import { useEffect, useState } from "react";

import { MainToolbar } from "@canonical/maas-react-components";
import { Button } from "@canonical/react-components";

import AddRack from "../AddRack/AddRack";

import DebounceSearchBox from "@/app/base/components/DebounceSearchBox";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { SetSearchFilter } from "@/app/base/types";

type Props = {
  searchFilter: string;
  setSearchFilter: SetSearchFilter;
};

const RacksListHeader = ({ searchFilter, setSearchFilter }: Props) => {
  const { openSidePanel } = useSidePanel();
  const [searchText, setSearchText] = useState(searchFilter);
  useEffect(() => {
    // If the filters change then update the search input text.
    setSearchText(searchFilter);
  }, [searchFilter]);

  return (
    <MainToolbar>
      <MainToolbar.Title>Racks</MainToolbar.Title>
      <MainToolbar.Controls>
        <DebounceSearchBox
          onDebounced={(debouncedText) => {
            setSearchFilter(debouncedText);
          }}
          searchText={searchText}
          setSearchText={setSearchText}
        />{" "}
        <Button
          data-testid="add-rack"
          key="add-rack"
          onClick={() => {
            openSidePanel({ component: AddRack, title: "Add rack" });
          }}
        >
          Add rack
        </Button>
      </MainToolbar.Controls>
    </MainToolbar>
  );
};

export default RacksListHeader;
