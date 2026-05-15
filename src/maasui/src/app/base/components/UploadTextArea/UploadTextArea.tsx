import type { ChangeEvent } from "react";
import { useState } from "react";

import { formatBytes } from "@canonical/maas-react-components";
import type { TextareaProps } from "@canonical/react-components";
import { Icon, Textarea } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useDropzone } from "react-dropzone";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import { useId } from "@/app/base/hooks/base";
import type { AnyObject } from "@/app/base/types";

type Props<V> = Omit<
  TextareaProps,
  | "aria-labelledby"
  | "autoCapitalize"
  | "autoComplete"
  | "autoCorrect"
  | "label"
  | "onChange"
  | "spellCheck"
> & {
  label: string;
  maxSize?: number;
  name: keyof V;
};

const MAX_SIZE_BYTES = 2000000;

export const UploadTextArea = <V extends AnyObject>({
  label,
  maxSize = MAX_SIZE_BYTES,
  name,
  ...textAreaProps
}: Props<V>): React.ReactElement => {
  const id = useId();
  const [fileErrors, setFileErrors] = useState<string | null>(null);
  const { handleChange, setFieldTouched, setFieldValue } =
    useFormikContext<V>();

  const handleUpload = (files: File[] | null) => {
    setFieldTouched(name, true).catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        name,
        "setFieldTouched",
        reason as string
      );
    });
    setFileErrors(null);

    if (!files || files.length === 0) {
      setFileErrors("No file was selected.");
      return;
    }
    if (files.length !== 1) {
      setFileErrors("Only one file can be selected at a time.");
      return;
    }
    const file = files[0];
    if (file.size > maxSize) {
      const byteSize = formatBytes({ value: maxSize, unit: "B" });
      setFileErrors(
        `File cannot be larger than ${byteSize.value}${byteSize.unit}.`
      );
      return;
    }

    const reader = new FileReader();
    reader.onerror = () => {
      setFileErrors("Error reading file.");
      reader.abort();
    };
    reader.onloadend = () => {
      if (typeof reader.result === "string") {
        setFieldValue(name, reader.result).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            name,
            "setFieldValue",
            reason as string
          );
        });
      } else {
        setFileErrors("Only text files are supported.");
        reader.abort();
      }
    };
    reader.readAsText(file);
  };

  const { getInputProps, getRootProps } = useDropzone({
    multiple: false,
    noClick: true,
    noKeyboard: true,
    onDropAccepted: handleUpload,
  });

  return (
    <div {...getRootProps()}>
      <label className="p-button" id={id}>
        <span className="u-nudge-left--small">
          <Icon name="back-to-top" />
        </span>
        {label}
        <input {...getInputProps()} />
      </label>
      <FormikField
        aria-labelledby={id}
        autoCapitalize="off"
        autoComplete="off"
        autoCorrect="off"
        component={Textarea}
        error={fileErrors}
        name={name}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => {
          handleChange(e);
          if (fileErrors) {
            // Clear the errors if the text has been changed.
            setFileErrors(null);
          }
        }}
        spellCheck="false"
        {...textAreaProps}
      />
    </div>
  );
};

export default UploadTextArea;
