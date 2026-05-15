import { ContentSection } from "@canonical/maas-react-components";
import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";

import VMWareForm from "../VMWareForm";

import { useConfigurations } from "@/app/api/query/configurations";
import type { PublicConfigName } from "@/app/apiclient";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { ConfigNames } from "@/app/store/config/types";

export enum Labels {
  Loading = "Loading...",
}

const VMWare = (): React.ReactElement => {
  const names = [
    ConfigNames.VCENTER_SERVER,
    ConfigNames.VCENTER_USERNAME,
    ConfigNames.VCENTER_PASSWORD,
    ConfigNames.VCENTER_DATACENTER,
  ] as PublicConfigName[];
  const { isPending, error, isSuccess } = useConfigurations({
    query: { name: names },
  });
  useWindowTitle("VMWare");

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          VMware
        </ContentSection.Title>
        <ContentSection.Content>
          {isPending && <Spinner text={Labels.Loading} />}
          {error && (
            <NotificationBanner
              severity="negative"
              title="Error while fetching image configurations"
            >
              {error.message}
            </NotificationBanner>
          )}
          {isSuccess && <VMWareForm />}
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default VMWare;
