import type { ReactElement } from "react";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { SSLKeysTable } from "@/app/preferences/views/SSLKeys/components";

const SSLKeysList = (): ReactElement => {
  useWindowTitle("SSL keys");

  return (
    <PageContent>
      <SSLKeysTable />
    </PageContent>
  );
};

export default SSLKeysList;
