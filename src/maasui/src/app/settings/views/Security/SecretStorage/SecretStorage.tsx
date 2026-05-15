import { ContentSection } from "@canonical/maas-react-components";
import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import VaultSettings from "./VaultSettings";

import PageContent from "@/app/base/components/PageContent";
import { useFetchActions, useWindowTitle } from "@/app/base/hooks";
import { generalActions } from "@/app/store/general";
import { vaultEnabled as vaultEnabledSelectors } from "@/app/store/general/selectors";

const SecretStorage = (): React.ReactElement => {
  const vaultEnabledLoaded = useSelector(vaultEnabledSelectors.loaded);
  useWindowTitle("Secret storage");

  useFetchActions([generalActions.fetchVaultEnabled]);

  if (!vaultEnabledLoaded) {
    return <Spinner text="Loading..." />;
  }

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          Secret storage
        </ContentSection.Title>
        <ContentSection.Content>
          <VaultSettings />
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default SecretStorage;
