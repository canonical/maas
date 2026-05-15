import { ContentSection } from "@canonical/maas-react-components";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import LicenseKeyTable from "@/app/settings/views/LicenseKeys/components/LicenseKeyTable/LicenseKeyTable";

const LicenseKeyList = (): React.ReactElement => {
  useWindowTitle("License keys");

  return (
    <PageContent>
      <ContentSection>
        <ContentSection.Content>
          <LicenseKeyTable />
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default LicenseKeyList;
