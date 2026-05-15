import { useState, type ReactElement } from "react";

import RacksListHeader from "../components/RacksListHeader/RacksListHeader";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { RacksTable } from "@/app/racks/components";

const RacksList = (): ReactElement => {
  useWindowTitle("Racks");

  const [searchText, setSearchText] = useState("");

  return (
    <PageContent
      header={
        <RacksListHeader
          searchFilter={searchText}
          setSearchFilter={setSearchText}
        />
      }
    >
      <RacksTable />
    </PageContent>
  );
};

export default RacksList;
