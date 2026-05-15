import { ContentSection } from "@canonical/maas-react-components";
import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";

import ThirdPartyDriversForm from "../ThirdPartyDriversForm";

import { useGetConfiguration } from "@/app/api/query/configurations";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { ConfigNames } from "@/app/store/config/types";

export enum Labels {
  Loading = "Loading...",
}

const ThirdPartyDrivers = (): React.ReactElement => {
  const { isPending, error, isSuccess } = useGetConfiguration({
    path: { name: ConfigNames.ENABLE_THIRD_PARTY_DRIVERS },
  });

  useWindowTitle("Ubuntu");

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          Ubuntu
        </ContentSection.Title>
        <ContentSection.Content>
          {isPending && <Spinner text="Loading..." />}
          {error && (
            <NotificationBanner
              severity="negative"
              title="Error while fetching image configurations"
            >
              {error.message}
            </NotificationBanner>
          )}
          {isSuccess && <ThirdPartyDriversForm />}
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default ThirdPartyDrivers;
