import { Col, List, Row, Textarea } from "@canonical/react-components";
import type { FormikProps } from "formik";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { RepositoryFormValues } from "../types";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import {
  componentsToDisable as componentsToDisableSelectors,
  knownArchitectures as knownArchitecturesSelectors,
  pocketsToDisable as pocketsToDisableSelectors,
} from "@/app/store/general/selectors";

type Props = {
  type: "ppa" | "repository";
};

export enum Labels {
  Arches = "Architectures",
  DisabledPockets = "Disabled pockets",
  DisabledComponents = "Disabled components",
  Name = "Name",
  URL = "URL",
  EnableRepo = "Enable repository",
  EnableSources = "Enable sources",
  Key = "Key",
  Distributions = "Distributions",
  Components = "Components",
}

const generateCheckboxGroup = (
  key: keyof RepositoryFormValues,
  fields: string[],
  label: string,
  setFieldTouched: FormikProps<RepositoryFormValues>["setFieldTouched"],
  setFieldValue: FormikProps<RepositoryFormValues>["setFieldValue"],
  values: string[]
) => {
  const checkboxes = fields.map((field) => (
    <FormikField
      checked={values.includes(field)}
      key={field}
      label={field}
      name={key}
      onChange={() => {
        let newFields: string[];
        if (values.includes(field)) {
          newFields = values.filter((oldField) => oldField !== field);
        } else {
          // Conserve original order of fields
          const temp = [...values, field];
          newFields = fields.filter((oldField) => temp.includes(oldField));
        }
        setFieldValue(key, newFields).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            key,
            "setFieldValue",
            reason as string
          );
        });
        setFieldTouched(key, true).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            key,
            "setFieldTouched",
            reason as string
          );
        });
      }}
      type="checkbox"
      value={field}
      wrapperClassName="u-no-margin--bottom"
    />
  ));

  return (
    <List aria-label={label} className="is-split--small" items={checkboxes} />
  );
};

const RepositoryFormFields = ({ type }: Props): React.ReactElement => {
  const { setFieldTouched, setFieldValue, values } =
    useFormikContext<RepositoryFormValues>();
  const componentsToDisable = useSelector(componentsToDisableSelectors.get);
  const knownArchitectures = useSelector(knownArchitecturesSelectors.get);
  const pocketsToDisable = useSelector(pocketsToDisableSelectors.get);

  return (
    <Row>
      <Col size={8}>
        <FormikField
          disabled={values.default}
          label={Labels.Name}
          name="name"
          required
          type="text"
        />
        <FormikField label={Labels.URL} name="url" required type="text" />
        <List
          className="is-split--small u-hide--medium u-hide--large"
          items={[
            <FormikField
              checked={values.enabled}
              disabled={values.default}
              label={Labels.EnableRepo}
              name="enabled"
              type="checkbox"
              wrapperClassName="u-no-margin--bottom"
            />,
            <FormikField
              checked={!values.disable_sources}
              label={Labels.EnableSources}
              name="disable_sources"
              onChange={() => {
                setFieldValue("disable_sources", !values.disable_sources).catch(
                  (reason: unknown) => {
                    throw new FormikFieldChangeError(
                      "disable_sources",
                      "setFieldValue",
                      reason as string
                    );
                  }
                );
              }}
              type="checkbox"
              wrapperClassName="u-no-margin--bottom"
            />,
          ]}
        />
        <FormikField
          component={Textarea}
          label={Labels.Key}
          name="key"
          style={{ height: "10rem", maxWidth: "100%" }}
        />
        {type === "repository" && !values.default && (
          <>
            <FormikField
              label="Distributions"
              name="distributions"
              type="text"
            />
            <FormikField label="Components" name="components" type="text" />
          </>
        )}
      </Col>
      <Col size={3}>
        <List
          className="is-split--small u-hide--small"
          items={[
            <FormikField
              checked={values.enabled}
              disabled={values.default}
              label={Labels.EnableRepo}
              name="enabled"
              type="checkbox"
              wrapperClassName="u-no-margin--bottom"
            />,
            <FormikField
              checked={!values.disable_sources}
              label={Labels.EnableSources}
              name="disable_sources"
              onChange={() => {
                setFieldValue("disable_sources", !values.disable_sources).catch(
                  (reason: unknown) => {
                    throw new FormikFieldChangeError(
                      "disable_sources",
                      "setFieldValue",
                      reason as string
                    );
                  }
                );
              }}
              type="checkbox"
              wrapperClassName="u-no-margin--bottom"
            />,
          ]}
        />
        <p className="u-no-margin--bottom">{Labels.Arches}</p>
        {generateCheckboxGroup(
          "arches",
          knownArchitectures,
          Labels.Arches,
          setFieldTouched,
          setFieldValue,
          values.arches
        )}
        {values.default && (
          <>
            <p className="u-no-margin--bottom">{Labels.DisabledPockets}</p>
            {generateCheckboxGroup(
              "disabled_pockets",
              pocketsToDisable,
              Labels.DisabledPockets,
              setFieldTouched,
              setFieldValue,
              values.disabled_pockets
            )}
            <p className="u-no-margin--bottom">{Labels.DisabledComponents}</p>
            {generateCheckboxGroup(
              "disabled_components",
              componentsToDisable,
              Labels.DisabledComponents,
              setFieldTouched,
              setFieldValue,
              values.disabled_components
            )}
          </>
        )}
      </Col>
    </Row>
  );
};

export default RepositoryFormFields;
