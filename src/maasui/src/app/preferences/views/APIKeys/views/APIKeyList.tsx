import { ContentSection, MainToolbar } from "@canonical/maas-react-components";
import { Button } from "@canonical/react-components";

import { APIKeyAdd, APIKeyTable } from "../components";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";

const APIKeyList = () => {
  useWindowTitle("API keys");
  const { openSidePanel } = useSidePanel();

  return (
    <PageContent>
      <ContentSection>
        <ContentSection.Header>
          <MainToolbar>
            <MainToolbar.Controls>
              <Button
                onClick={() => {
                  openSidePanel({
                    component: APIKeyAdd,
                    title: "Generate MAAS API key",
                  });
                }}
              >
                Generate MAAS API key
              </Button>
            </MainToolbar.Controls>
          </MainToolbar>
        </ContentSection.Header>
        <ContentSection.Content>
          <APIKeyTable />
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default APIKeyList;
