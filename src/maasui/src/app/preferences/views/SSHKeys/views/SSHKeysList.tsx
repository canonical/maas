import type { ReactElement } from "react";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { SSHKeysTable } from "@/app/preferences/views/SSHKeys/components";

type SSHKeysListProps = {
  isIntro?: boolean;
};

const SSHKeysList = ({ isIntro = false }: SSHKeysListProps): ReactElement => {
  useWindowTitle("SSH Keys");

  return (
    <>
      {isIntro ? (
        <SSHKeysTable isIntro={true} />
      ) : (
        <PageContent>
          <SSHKeysTable isIntro={false} />
        </PageContent>
      )}
    </>
  );
};

export default SSHKeysList;
