import type { ReactElement } from "react";

import { FileUpload } from "@canonical/maas-react-components";
import type { SelectProps } from "@canonical/react-components";
import { Input, Label, Select, Strip } from "@canonical/react-components";
import classNames from "classnames";
import type { FormikProps } from "formik";
import { Field } from "formik";
import { sha256 } from "js-sha256";
import type { FileRejection } from "react-dropzone";
import * as Yup from "yup";

import { useUploadCustomImage } from "@/app/api/query/images";
import type {
  BootResourceFileTypeChoice,
  UploadCustomImageError,
} from "@/app/apiclient";
import FormikField, {
  FormikFieldChangeError,
} from "@/app/base/components/FormikField/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import {
  ARCHITECTURES,
  BASE_IMAGE_OPERATING_SYSTEM_NAMES,
  OPERATING_SYSTEM_NAMES,
  VALID_IMAGE_FILE_TYPES,
} from "@/app/images/constants";

type UploadImageFormValues = {
  title: string;
  release: string;
  os: string;
  arch: string;
  file: File | undefined;
  baseImageOs: string;
  baseImageRelease: string;
};

export const getChecksumSha256 = async (file: Blob | File) => {
  const arrayBuffer = await file.arrayBuffer();
  return sha256(arrayBuffer);
};

export const getFileExtension = (
  fileName: string
): BootResourceFileTypeChoice => {
  return fileName.split(".").pop()?.toLowerCase() as BootResourceFileTypeChoice;
};

const osOptions: SelectProps["options"] = [
  {
    label: "Select an operating system",
    value: "",
    disabled: true,
  },
  ...OPERATING_SYSTEM_NAMES,
];

const baseImageOsOptions: SelectProps["options"] = [
  {
    label: "Select an operating system",
    value: "",
    disabled: true,
  },
  ...BASE_IMAGE_OPERATING_SYSTEM_NAMES,
];

const archOptions: SelectProps["options"] = [
  {
    label: "Select an architecture",
    value: "",
    disabled: true,
  },
  ...ARCHITECTURES,
];

const UploadImageSchema = Yup.object().shape({
  title: Yup.string().required("Release title is required."),
  release: Yup.string().required("Release is required."),
  os: Yup.string().required("OS is required."),
  arch: Yup.string().required("Architecture is required."),
  file: Yup.mixed<File>().required("Image file is required."),
  baseImageOs: Yup.string().when("os", {
    is: "Custom",
    then: (schema) => schema.required("Base image OS is required."),
  }),
  baseImageRelease: Yup.string().when("os", {
    is: "Custom",
    then: (schema) => schema.required("Base image release is required."),
  }),
});

const UploadCustomImage = (): ReactElement => {
  const { closeSidePanel } = useSidePanel();

  const uploadCustomImage = useUploadCustomImage();

  return (
    <div className="upload-custom-image-form">
      <Strip shallow>
        <FormikForm<UploadImageFormValues, UploadCustomImageError>
          buttonsBehavior="independent"
          enableReinitialize
          errors={uploadCustomImage.error}
          initialValues={
            {
              title: "",
              release: "",
              os: "",
              arch: "",
              file: undefined,
              baseImageOs: "",
              baseImageRelease: "",
            } as UploadImageFormValues
          }
          onCancel={closeSidePanel}
          onSubmit={async (values) => {
            if (values.file) {
              const sha256 = await getChecksumSha256(values.file);
              const baseImage =
                values.baseImageOs && values.baseImageRelease
                  ? `${values.baseImageOs}/${values.baseImageRelease}`
                  : undefined;
              uploadCustomImage.mutate({
                body: values.file,
                headers: {
                  "Content-Type": "multipart/form-data",
                  name: `${values.os.toLowerCase()}/${values.release}`,
                  sha256,
                  size: values.file.size,
                  architecture: `${values.arch}/generic`,
                  "file-type": getFileExtension(values.file.name),
                  title: values.title,
                  "base-image": baseImage,
                },
              });
            }
          }}
          onSuccess={closeSidePanel}
          saved={uploadCustomImage.isSuccess}
          saving={uploadCustomImage.isPending}
          submitLabel="Upload"
          validateOnChange
          validationSchema={UploadImageSchema}
        >
          {({
            errors,
            touched,
            values,
            setFieldValue,
            setFieldTouched,
            setFieldError,
          }: FormikProps<UploadImageFormValues>) => (
            <>
              <FormikField
                aria-label="Operating system"
                component={Select}
                error={touched.os && errors.os}
                help="The operating system of the image."
                label="Operating system"
                name="os"
                options={osOptions}
                required
              />
              <FormikField
                aria-label="Release title"
                component={Input}
                error={touched.title && errors.title}
                help="The release title that will be shown in the images table, e.g. 24.04 LTS."
                label="Release title"
                name="title"
                required
                type="text"
              />
              <FormikField
                aria-label="Release codename"
                component={Input}
                error={touched.release && errors.release}
                help="The codename for the release, e.g. 'noble'."
                label="Release codename"
                name="release"
                required
                type="text"
              />
              <FormikField
                aria-label="Architecture"
                component={Select}
                error={touched.arch && errors.arch}
                label="Architecture"
                name="arch"
                options={archOptions}
                required
              />
              {values.os === "Custom" && (
                <>
                  <div className="u-sv2">
                    <hr className="u-sv2" />
                  </div>
                  <FormikField
                    aria-label="Base image operating system"
                    component={Select}
                    error={touched.baseImageOs && errors.baseImageOs}
                    help="The operating system that the custom image is based on."
                    label="Base image operating system"
                    name="baseImageOs"
                    options={baseImageOsOptions}
                    required
                  />
                  <FormikField
                    aria-label="Base image release codename"
                    component={Input}
                    error={touched.baseImageRelease && errors.baseImageRelease}
                    help="The codename for the base image release."
                    label="Base image release codename"
                    name="baseImageRelease"
                    required
                    type="text"
                  />
                  <div className="u-sv2">
                    <hr className="u-sv2" />
                  </div>
                </>
              )}
              <div
                className={classNames("p-form__group p-form-validation", {
                  "is-error": touched.file && errors.file,
                })}
              >
                <Label className="is-required" id="file-field">
                  Upload image
                </Label>
                <p className="p-form-help-text">
                  Supported file types are tgz, tbz, txz, ddtgz, ddtbz, ddtxz,
                  ddtar, ddbz2, ddgz, ddxz and ddraw.
                </p>
                <div className="p-form__control">
                  <div className="u-padding-bottom--medium">
                    <Field
                      accept={VALID_IMAGE_FILE_TYPES}
                      aria-labelledby="file-field"
                      as={FileUpload}
                      error={touched.file && errors.file}
                      files={values.file && !errors.file ? [values.file] : []}
                      maxFiles={1}
                      name="file"
                      onFileUpload={async (
                        files: File[],
                        rejectedFiles: FileRejection[]
                      ) => {
                        setFieldTouched("file", true).catch(
                          (reason: unknown) => {
                            throw new FormikFieldChangeError(
                              "file",
                              "setFieldTouched",
                              reason as string
                            );
                          }
                        );
                        if (files.length) {
                          setFieldValue("file", files[0])
                            // Clear errors if file is valid
                            .then(() => {
                              setFieldError("file", undefined);
                            })
                            .catch((reason: unknown) => {
                              throw new FormikFieldChangeError(
                                "file",
                                "setFieldValue",
                                reason as string
                              );
                            });
                        } else {
                          setFieldValue("file", rejectedFiles[0].file)
                            // Set error to rejected file's message
                            .then(() => {
                              setFieldError(
                                "file",
                                `${rejectedFiles[0].errors[0].message.replace(
                                  "application/octet-stream,",
                                  ""
                                )}.`
                              );
                            })
                            .catch((reason: unknown) => {
                              throw new FormikFieldChangeError(
                                "file",
                                "setFieldValue",
                                reason as string
                              );
                            });
                        }
                      }}
                      onRemoveFile={async () => {
                        setFieldValue("file", undefined).catch(
                          (reason: unknown) => {
                            throw new FormikFieldChangeError(
                              "file",
                              "setFieldTouched",
                              reason as string
                            );
                          }
                        );
                      }}
                      rejectedFiles={
                        values.file && errors.file
                          ? [
                              {
                                file: values.file,
                                errors: [
                                  {
                                    code: "validation-error",
                                    message: errors.file as string,
                                  },
                                ],
                              },
                            ]
                          : []
                      }
                      required
                      validate={() => {
                        // Force return the previous state's errors so that
                        // form re-validation does not clear field-level errors.
                        return errors.file;
                      }}
                    />
                  </div>
                </div>
              </div>
            </>
          )}
        </FormikForm>
      </Strip>
    </div>
  );
};

export default UploadCustomImage;
