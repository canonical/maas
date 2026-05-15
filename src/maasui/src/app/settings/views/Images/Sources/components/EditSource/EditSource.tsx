import type { ReactElement } from "react";
import React, { useMemo, useState } from "react";

import {
  Icon,
  Notification as NotificationBanner,
  Select,
  Spinner,
  Textarea,
  Tooltip,
} from "@canonical/react-components";
import type { FormikContextType } from "formik";

import {
  useFetchImageSource,
  useGetImageSource,
  useUpdateImageSource,
} from "@/app/api/query/imageSources";
import type {
  BootSourceResponse,
  NotFoundBodyResponse,
  ValidationErrorBodyResponse,
} from "@/app/apiclient";
import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { SourceValues } from "@/app/settings/views/Images/Sources/components/AddSource/AddSource";
import { SourceSchema } from "@/app/settings/views/Images/Sources/components/AddSource/AddSource";
import { Labels } from "@/app/settings/views/Images/Sources/constants";

type EditSourceProps = {
  id: number;
  isDefault: boolean;
};

const getInitialKeyringType = (
  source: BootSourceResponse
): "keyring_data" | "keyring_filename" | "keyring_unsigned" => {
  if (source.keyring_filename) return "keyring_filename";
  if (source.keyring_data) return "keyring_data";
  return "keyring_unsigned";
};

const EditSource = ({ id, isDefault }: EditSourceProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();

  const source = useGetImageSource({ path: { boot_source_id: id } }, true);

  const eTag = source.data?.headers?.get("ETag");

  const initialValues = useMemo<SourceValues>(
    () => ({
      name: source.data?.name ?? "",
      url: source.data?.url ?? "",
      keyring_type: source.data
        ? getInitialKeyringType(source.data)
        : "keyring_unsigned",
      keyring_filename: source.data?.keyring_filename ?? "",
      keyring_data: source.data?.keyring_data ?? "",
      skip_keyring_verification: source.data?.skip_keyring_verification,
      priority: source.data?.priority ?? 10,
      enabled: source.data?.enabled ?? true,
    }),
    [source.data]
  );

  const [isValidated, setIsValidated] = useState(false);
  const [lastValidatedValues, setLastValidatedValues] =
    useState<SourceValues | null>(null);

  const updateSource = useUpdateImageSource();
  const fetchImageSource = useFetchImageSource();

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
    updateSource.error || fetchImageSource.error
      ? ((updateSource.error ?? fetchImageSource.error) as
          | NotFoundBodyResponse
          | ValidationErrorBodyResponse
          | null)
      : null;

  return (
    <>
      {source.isPending && <Spinner text="Loading..." />}
      {source.isError && (
        <NotificationBanner severity="negative">
          {source.error.message}
        </NotificationBanner>
      )}
      {source.isSuccess && source.data && (
        <FormikForm<
          SourceValues,
          NotFoundBodyResponse | ValidationErrorBodyResponse | null
        >
          aria-label="Edit source"
          buttonsBehavior="independent"
          enableReinitialize
          errors={errors}
          initialValues={initialValues}
          onCancel={closeSidePanel}
          onSubmit={(values) => {
            updateSource.mutate(
              {
                headers: { ETag: eTag },
                path: { boot_source_id: id },
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
                    values.keyring_type === "keyring_unsigned"
                      ? true
                      : undefined,
                  priority: values.priority,
                  enabled: values.enabled,
                },
              },
              { onSuccess: closeSidePanel }
            );
          }}
          onValuesChanged={onValuesChanged}
          saved={updateSource.isSuccess}
          saving={updateSource.isPending}
          secondarySubmit={!isDefault ? onValidate : undefined}
          secondarySubmitLabel={
            !isValidated && !isDefault ? "Validate" : undefined
          }
          secondarySubmitSaved={isValidated}
          secondarySubmitSaving={fetchImageSource.isPending}
          submitDisabled={!isValidated && !isDefault}
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
                {!isDefault && (
                  <>
                    <FormikField
                      label={Labels.Name}
                      name="name"
                      required
                      type="text"
                    />
                    <FormikField
                      aria-label={Labels.Url}
                      disabled
                      label={
                        <>
                          {Labels.Url}
                          <Tooltip
                            className="u-nudge-right--small"
                            message="Source URL is immutable. You must delete this source, and create a new one to change the URL."
                          >
                            <Icon name="help" />
                          </Tooltip>
                        </>
                      }
                      name="url"
                      type="text"
                    />
                    <Select
                      label="Keyring"
                      name="keyring_type"
                      onChange={async (
                        e: React.ChangeEvent<HTMLSelectElement>
                      ) => {
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
                        {
                          label: "Keyring filename",
                          value: "keyring_filename",
                        },
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
                  </>
                )}
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
      )}
    </>
  );
};

export default EditSource;
