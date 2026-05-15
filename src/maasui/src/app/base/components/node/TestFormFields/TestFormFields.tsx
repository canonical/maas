import * as React from "react";

import { Col, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";
import * as Yup from "yup";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import TagSelector from "@/app/base/components/TagSelector";
import type { Tag } from "@/app/base/components/TagSelector/TagSelector";
import type { Script } from "@/app/store/script/types";
import { getObjectString } from "@/app/store/script/utils";

export type TestFormValues = {
  enableSSH: boolean;
  scripts: Script[];
  scriptInputs: Record<string, { url: string }>;
};

type ScriptsDisplay = Script & { displayName: string };
type Props = {
  modelName: string;
  preselected: ScriptsDisplay[];
  scripts: Script[];
};

export const TestFormSchema = Yup.object().shape({
  enableSSH: Yup.boolean(),
  scripts: Yup.array()
    .of(
      Yup.object().shape({
        name: Yup.string().required(),
        displayName: Yup.string(),
        description: Yup.string(),
      })
    )
    .min(1, "You must select at least one script.")
    .required(),
  urls: Yup.object(),
});

export const TestFormFields = ({
  modelName,
  preselected,
  scripts,
}: Props): React.ReactElement => {
  const { handleChange, setFieldValue, values } =
    useFormikContext<TestFormValues>();
  const urlScriptsSelected = values.scripts.filter((script) =>
    Object.keys(script.parameters).some((key) => key === "url")
  );

  return (
    <Row>
      <Col size={12}>
        <FormikField
          label={`Allow SSH access and prevent ${modelName} powering off`}
          name="enableSSH"
          type="checkbox"
        />
        <FormikField
          component={TagSelector}
          disabled={values.scripts.length === scripts.length}
          initialSelected={preselected}
          label="Tests"
          name="tests"
          onTagsUpdate={(tags: Tag[]) => {
            const selectedScripts = tags.map((tag) =>
              scripts.find((script) => script.id === tag.id)
            );
            setFieldValue("scripts", selectedScripts).catch(
              (reason: unknown) => {
                throw new FormikFieldChangeError(
                  "scripts",
                  "setFieldValue",
                  reason as string
                );
              }
            );
          }}
          placeholder="Select scripts"
          tags={scripts.map(({ id, name }) => ({
            id,
            name,
          }))}
        />
        {urlScriptsSelected.map((script) => (
          <FormikField
            data-testid="url-script-input"
            help={getObjectString(script.parameters.url, "description")}
            key={script.name}
            label={
              <span>
                URL(s) to use for <strong>{script.name}</strong> script
              </span>
            }
            name={`scriptInputs[${script.name}].url`}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
              handleChange(e);
              setFieldValue(
                `scriptInputs[${script.name}].url`,
                e.target.value
              ).catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  `scriptInputs[${script.name}].url`,
                  "setFieldValue",
                  reason as string
                );
              });
            }}
            type="text"
          />
        ))}
      </Col>
    </Row>
  );
};

export default TestFormFields;
