import { useEffect, useState } from "react";

import { MainToolbar } from "@canonical/maas-react-components";
import { Button } from "@canonical/react-components";

import DebounceSearchBox from "@/app/base/components/DebounceSearchBox";
import type { SetSearchFilter } from "@/app/base/types";

type Props = {
  searchFilter: string;
  setSearchFilter: SetSearchFilter;
};

const SwitchesListHeader = ({ searchFilter, setSearchFilter }: Props) => {
  const [searchText, setSearchText] = useState(searchFilter);

  useEffect(() => {
    setSearchText(searchFilter);
  }, [searchFilter]);

  return (
    <MainToolbar>
      <MainToolbar.Title>Switches</MainToolbar.Title>
      <MainToolbar.Controls>
        {/* TODO: Wire up search to the switches endpoint when it becomes available. */}
        <DebounceSearchBox
          onDebounced={(debouncedText) => {
            setSearchFilter(debouncedText);
          }}
          searchText={searchText}
          setSearchText={setSearchText}
        />
        <Button data-testid="add-switch">Add switch</Button>
      </MainToolbar.Controls>
    </MainToolbar>
  );
};

export default SwitchesListHeader;
