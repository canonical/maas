import type { ReactElement } from "react";

import { ContentSection, MainToolbar } from "@canonical/maas-react-components";
import { Button } from "@canonical/react-components";

import type { BootSourceResponse } from "@/app/apiclient";
import PageContent from "@/app/base/components/PageContent";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { BootResourceSourceType } from "@/app/images/types";
import AddSource from "@/app/settings/views/Images/Sources/components/AddSource";
import SourcesTable from "@/app/settings/views/Images/Sources/components/SourcesTable";

export type ImageSource = BootSourceResponse & {
  type: BootResourceSourceType;
};

const Sources = (): ReactElement => {
  const { openSidePanel } = useSidePanel();

  return (
    <PageContent>
      <ContentSection variant="wide">
        <ContentSection.Header>
          <MainToolbar>
            <MainToolbar.Title>Sources</MainToolbar.Title>
            <MainToolbar.Controls>
              <Button
                onClick={() => {
                  openSidePanel({
                    component: AddSource,
                    title: "Add custom source",
                  });
                }}
              >
                Add custom source
              </Button>
            </MainToolbar.Controls>
          </MainToolbar>
        </ContentSection.Header>
        <ContentSection.Content>
          <SourcesTable />
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default Sources;
