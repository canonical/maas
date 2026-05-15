import type { ReactNode } from "react";
import { useState } from "react";

import type { PropsWithSpread } from "@canonical/react-components";
import { Button } from "@canonical/react-components";

import type { Props as TitledSectionProps } from "@/app/base/components/TitledSection";
import TitledSection from "@/app/base/components/TitledSection";

type Props = PropsWithSpread<
  {
    canEdit?: boolean;
    renderContent: (
      editing: boolean,
      setEditing: (editing: boolean) => void
    ) => ReactNode;
  },
  Omit<TitledSectionProps, "children">
>;

export enum Labels {
  EditButton = "Edit",
}

const EditableSection = ({
  canEdit = true,
  renderContent,
  ...titledSectionProps
}: Props): React.ReactElement => {
  const [editing, setEditing] = useState(false);
  const showEditButton = canEdit && !editing;

  return (
    <TitledSection
      buttons={
        showEditButton ? (
          <Button
            className="u-no-margin--bottom"
            onClick={() => {
              setEditing(true);
            }}
          >
            {Labels.EditButton}
          </Button>
        ) : null
      }
      {...titledSectionProps}
    >
      {renderContent(editing, setEditing)}
    </TitledSection>
  );
};

export default EditableSection;
