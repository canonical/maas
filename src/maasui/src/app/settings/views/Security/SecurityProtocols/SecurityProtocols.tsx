import { ContentSection } from "@canonical/maas-react-components";
import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import TLSDisabled from "./TLSDisabled";
import TLSEnabled from "./TLSEnabled";

import PageContent from "@/app/base/components/PageContent";
import { useFetchActions, useWindowTitle } from "@/app/base/hooks";
import { generalActions } from "@/app/store/general";
import { tlsCertificate as tlsCertificateSelectors } from "@/app/store/general/selectors";

const SecurityProtocols = (): React.ReactElement => {
  const tlsCertificate = useSelector(tlsCertificateSelectors.get);
  const tlsCertificateLoaded = useSelector(tlsCertificateSelectors.loaded);
  useWindowTitle("Security protocols");
  useFetchActions([generalActions.fetchTlsCertificate]);

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          Security protocols
        </ContentSection.Title>
        <ContentSection.Content>
          {!tlsCertificateLoaded ? (
            <Spinner text="Loading..." />
          ) : tlsCertificate ? (
            <TLSEnabled />
          ) : (
            <TLSDisabled />
          )}
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default SecurityProtocols;
