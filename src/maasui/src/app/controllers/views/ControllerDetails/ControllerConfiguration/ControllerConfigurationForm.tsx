import { useCallback } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import Definition from "@/app/base/components/Definition";
import EditableSection from "@/app/base/components/EditableSection";
import FormikForm from "@/app/base/components/FormikForm";
import NodeConfigurationFields, {
  NodeConfigurationSchema,
} from "@/app/base/components/NodeConfigurationFields";
import type { NodeConfigurationValues } from "@/app/base/components/NodeConfigurationFields";
import TagLinks from "@/app/base/components/TagLinks";
import { useFetchActions, useCanEdit } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors from "@/app/store/controller/selectors";
import {
  FilterControllers,
  isControllerDetails,
} from "@/app/store/controller/utils";
import { machineActions } from "@/app/store/machine";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";

type Props = { systemId: MachineDetails["system_id"] };

export enum Label {
  Title = "Controller configuration",
}

const ControllerConfigurationForm = ({
  systemId,
}: Props): React.ReactElement | null => {
  const dispatch = useDispatch();
  const node = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  const controllerTags = useSelector((state: RootState) =>
    tagSelectors.getByIDs(state, node?.tags || null)
  );
  const errors = useSelector(controllerSelectors.errors);
  const saved = useSelector(controllerSelectors.saved);
  const saving = useSelector(controllerSelectors.saving);
  const cleanup = useCallback(() => machineActions.cleanup(), []);
  const canEdit = useCanEdit(node, true);

  useFetchActions([tagActions.fetch]);

  if (!isControllerDetails(node)) {
    return <Spinner text="Loading..." />;
  }

  return (
    <EditableSection
      canEdit={canEdit}
      className="u-no-padding--top"
      hasSidebarTitle
      renderContent={(editing, setEditing) =>
        editing ? (
          <FormikForm<NodeConfigurationValues>
            aria-label={Label.Title}
            cleanup={cleanup}
            errors={errors}
            initialValues={{
              description: node.description || "",
              tags: node.tags,
              zone: node.zone?.name || "",
            }}
            onCancel={() => {
              setEditing(false);
            }}
            onSaveAnalytics={{
              action: "Configure controller",
              category: "Controller details",
              label: "Save changes",
            }}
            onSubmit={(values) => {
              const params = {
                description: values.description,
                system_id: systemId,
                tags: values.tags,
                zone: { name: values.zone },
              };
              dispatch(controllerActions.update(params));
            }}
            onSuccess={() => {
              setEditing(false);
            }}
            saved={saved}
            saving={saving}
            submitLabel="Save changes"
            validationSchema={NodeConfigurationSchema}
          >
            <NodeConfigurationFields />
          </FormikForm>
        ) : (
          <div data-testid="non-editable-controller-details">
            <Definition description={node.zone.name} label="Zone" />
            <Definition description={node.description} label="Note" />
            <Definition label="Tags">
              {node.tags.length ? (
                <TagLinks
                  getLinkURL={(tag) => {
                    const filter = FilterControllers.filtersToQueryString({
                      tags: [`=${tag.name}`],
                    });
                    return `${urls.controllers.index}${filter}`;
                  }}
                  tags={controllerTags}
                />
              ) : null}
            </Definition>
          </div>
        )
      }
      title={Label.Title}
    />
  );
};

export default ControllerConfigurationForm;
