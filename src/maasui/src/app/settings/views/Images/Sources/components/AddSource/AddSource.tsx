import type { ReactElement } from "react";
import React, { useEffect, useState } from "react";

import { Select, Textarea } from "@canonical/react-components";
import type { FormikContextType } from "formik";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import {
  useCreateImageSource,
  useFetchImageSource,
} from "@/app/api/query/imageSources";
import type {
  BootSourceCreateRequest,
  NotFoundBodyResponse,
  ValidationErrorBodyResponse,
} from "@/app/apiclient";
import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { MAAS_IO_DEFAULT_KEYRING_FILE_PATHS } from "@/app/images/constants";
import { Labels } from "@/app/settings/views/Images/Sources/constants";
import { generalActions } from "@/app/store/general";
import { installType } from "@/app/store/general/selectors";

export const SourceSchema = Yup.object()
  .shape({
    keyring_type: Yup.string()
      .oneOf(["keyring_data", "keyring_filename", "keyring_unsigned"])
      .required("Keyring type is required"),
    keyring_data: Yup.string().when("keyring_type", {
      is: "keyring_data",
      then: (schema) => schema.required("Keyring data is required"),
      otherwise: (schema) => schema,
    }),
    keyring_filename: Yup.string().when("keyring_type", {
      is: "keyring_filename",
      then: (schema) => schema.required("Keyring filename is required"),
      otherwise: (schema) => schema,
    }),
    url: Yup.string().required("URL is required"),
    autoSync: Yup.boolean(),
  })
  .defined();

export type SourceValues = BootSourceCreateRequest & {
  keyring_type: "keyring_data" | "keyring_filename" | "keyring_unsigned";
};

const AddSource = (): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const [isValidated, setIsValidated] = useState(false);
  const [lastValidatedValues, setLastValidatedValues] =
    useState<SourceValues | null>(null);

  const createSource = useCreateImageSource();
  const fetchImageSource = useFetchImageSource();

  const installTypeData = useSelector(installType.get);

  useEffect(() => {
    dispatch(generalActions.fetchInstallType());
  });

  const onValidate = async (values: SourceValues) => {
    if (!isValidated) {
      try {
        await fetchImageSource.mutateAsync(
          {
            body: {
              url: values.url,
              keyring_filename:
                values.keyring_type === "keyring_filename"
                  ? values.keyring_filename
                  : undefined,
              keyring_data:
                values.keyring_type === "keyring_data"
                  ? values.keyring_data
                  : undefined,
              skip_keyring_verification:
                values.keyring_type === "keyring_unsigned" ? true : undefined,
            },
          },
          {
            onSuccess: () => {
              setIsValidated(true);
              setLastValidatedValues(values);
            },
          }
        );
      } catch {
        // Error is surfaced via fetchImageSource.error / the errors variable
      }
      return;
    }
    setIsValidated(false);
  };

  const onValuesChanged = (values: SourceValues) => {
    if (
      lastValidatedValues &&
      JSON.stringify(values) !== JSON.stringify(lastValidatedValues)
    ) {
      setIsValidated(false);
    }
  };

  const errors =
    createSource.error || fetchImageSource.error
      ? ((createSource.error ?? fetchImageSource.error) as
          | NotFoundBodyResponse
          | ValidationErrorBodyResponse
          | null)
      : null;

  return (
    <FormikForm<
      SourceValues,
      NotFoundBodyResponse | ValidationErrorBodyResponse | null
    >
      aria-label="Add source"
      buttonsBehavior="independent"
      errors={errors}
      initialValues={{
        name: "",
        url: "",
        keyring_type: "keyring_filename",
        keyring_filename:
          installTypeData === "deb"
            ? MAAS_IO_DEFAULT_KEYRING_FILE_PATHS.deb
            : MAAS_IO_DEFAULT_KEYRING_FILE_PATHS.snap,
        keyring_data: "",
        skip_keyring_verification: undefined,
        priority: 10,
        enabled: true,
      }}
      onCancel={closeSidePanel}
      onSubmit={(values) => {
        createSource.mutate(
          {
            body: {
              name: values.name,
              url: values.url,
              keyring_filename:
                values.keyring_type === "keyring_filename"
                  ? values.keyring_filename
                  : undefined,
              keyring_data:
                values.keyring_type === "keyring_data"
                  ? values.keyring_data
                  : undefined,
              skip_keyring_verification:
                values.keyring_type === "keyring_unsigned" ? true : undefined,
              priority: values.priority,
              enabled: true,
            },
          },
          { onSuccess: closeSidePanel }
        );
      }}
      onValuesChanged={onValuesChanged}
      saved={createSource.isSuccess}
      saving={createSource.isPending}
      secondarySubmit={onValidate}
      secondarySubmitLabel={!isValidated ? "Validate" : undefined}
      secondarySubmitSaved={isValidated}
      secondarySubmitSaving={fetchImageSource.isPending}
      submitDisabled={!isValidated}
      submitLabel="Save source"
      validationSchema={SourceSchema}
    >
      {({
        setFieldValue,
        validateForm,
        values,
      }: FormikContextType<SourceValues>) => {
        return (
          <>
            <FormikField label={Labels.Name} name="name" required type="text" />
            <FormikField
              label={Labels.Url}
              name="url"
              placeholder="e.g. http:// or https://"
              required
              type="text"
            />
            <Select
              label="Keyring"
              name="keyring_type"
              onChange={async (e: React.ChangeEvent<HTMLSelectElement>) => {
                const newType = e.target.value as
                  | "keyring_data"
                  | "keyring_filename"
                  | "keyring_unsigned";
                await setFieldValue("keyring_type", newType).catch(
                  (reason: unknown) => {
                    throw new FormikFieldChangeError(
                      "keyring_type",
                      "setFieldValue",
                      reason as string
                    );
                  }
                );
                // Clear the other field when switching types
                if (newType === "keyring_filename") {
                  await setFieldValue("keyring_data", "").catch(
                    (reason: unknown) => {
                      throw new FormikFieldChangeError(
                        "keyring_data",
                        "setFieldValue",
                        reason as string
                      );
                    }
                  );
                } else if (newType === "keyring_data") {
                  await setFieldValue("keyring_filename", "").catch(
                    (reason: unknown) => {
                      throw new FormikFieldChangeError(
                        "keyring_filename",
                        "setFieldValue",
                        reason as string
                      );
                    }
                  );
                }
                await validateForm();
              }}
              options={[
                { label: "Keyring filename", value: "keyring_filename" },
                { label: "Keyring data", value: "keyring_data" },
                { label: "Unsigned", value: "keyring_unsigned" },
              ]}
              required
              value={values.keyring_type}
            />
            {values.keyring_type === "keyring_filename" ? (
              <FormikField
                aria-label={Labels.KeyringFilename}
                help="Path to the keyring to validate the mirror path."
                name="keyring_filename"
                placeholder="e.g. /usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"
                required
                type="text"
              />
            ) : values.keyring_type === "keyring_data" ? (
              <FormikField
                aria-label={Labels.KeyringData}
                component={Textarea}
                help="Contents on the keyring to validate the mirror path."
                name="keyring_data"
                placeholder="Contents of GPG key (base64 encoded)"
                required
              />
            ) : null}
            <FormikField
              help="If the same image is available from several sources, the image from the higher priority takes precedence. 1 is the lowest priority."
              label={Labels.Priority}
              name="priority"
              required
              type="number"
            />
          </>
        );
      }}
    </FormikForm>
  );
};

export default AddSource;
