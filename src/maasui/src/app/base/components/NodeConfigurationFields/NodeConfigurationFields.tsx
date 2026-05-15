import { useState } from "react";

import { Col, Modal, Row, Textarea } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";
import usePortal from "react-useportal";
import type { SchemaOf } from "yup";
import * as Yup from "yup";

import type { NodeConfigurationValues } from "./types";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import NodeTagForm from "@/app/base/components/NodeTagForm";
import TagIdField from "@/app/base/components/TagIdField";
import ZoneSelect from "@/app/base/components/ZoneSelect";
import type { RootState } from "@/app/store/root/types";
import tagSelectors from "@/app/store/tag/selectors";

export enum Label {
  AddTag = "Create a new tag",
  Note = "Note",
}

export const NodeConfigurationSchema: SchemaOf<NodeConfigurationValues> =
  Yup.object()
    .shape({
      description: Yup.string(),
      tags: Yup.array().of(Yup.number()),
      zone: Yup.string(),
    })
    .defined();

const NodeConfigurationFields = (): React.ReactElement => {
  const { openPortal, closePortal, isOpen, Portal } = usePortal();
  const { setFieldValue, values } = useFormikContext<NodeConfigurationValues>();
  const selectedTags = useSelector((state: RootState) =>
    tagSelectors.getByIDs(state, values.tags)
  );
  const [newTagName, setNewTagName] = useState<string | null>(null);
  const manualTags = useSelector(tagSelectors.getManual);

  return (
    <>
      <Row>
        <Col size={6}>
          <ZoneSelect name="zone" />
          <FormikField
            component={Textarea}
            label={Label.Note}
            name="description"
          />
          <TagIdField
            disabledTags={selectedTags.filter(
              (tag) => tag.definition.length > 0
            )}
            externalSelectedTags={selectedTags}
            name="tags"
            onAddNewTag={(name) => (event) => {
              setNewTagName(name);
              openPortal(event);
            }}
            placeholder="Create or remove tags"
            tagList={manualTags}
          />
        </Col>
      </Row>
      {isOpen ? (
        <Portal>
          <Modal
            className="tag-form__modal"
            close={() => closePortal()}
            title={Label.AddTag}
          >
            <NodeTagForm
              name={newTagName}
              onSaveAnalytics={{
                action: "Manual tag created",
                category: "Node configuration create tag form",
                label: "Save",
              }}
              onTagCreated={(tag) => {
                setFieldValue("tags", values.tags.concat([tag.id])).catch(
                  (reason: unknown) => {
                    throw new FormikFieldChangeError(
                      "tags",
                      "setFieldValue",
                      reason as string
                    );
                  }
                );
                setNewTagName(null);
                closePortal();
              }}
            />
          </Modal>
        </Portal>
      ) : null}
    </>
  );
};

export default NodeConfigurationFields;
