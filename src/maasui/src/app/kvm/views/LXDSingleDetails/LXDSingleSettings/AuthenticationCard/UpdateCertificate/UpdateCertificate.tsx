import { useEffect, useState } from "react";

import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import UpdateCertificateFields from "./UpdateCertificateFields";

import type { FormikFormProps } from "@/app/base/components/FormikForm";
import FormikForm from "@/app/base/components/FormikForm";
import { generalActions } from "@/app/store/general";
import { generatedCertificate as generatedCertificateSelectors } from "@/app/store/general/selectors";
import { podActions } from "@/app/store/pod";
import podSelectors from "@/app/store/pod/selectors";
import type { PodDetails } from "@/app/store/pod/types";

type Props = {
  closeForm: () => void;
  hasCertificateData: boolean;
  objectName?: string | null;
  pod: PodDetails;
};

export type UpdateCertificateValues = {
  certificate: string;
  key: string;
  password: string;
};

const UpdateCertificate = ({
  closeForm,
  hasCertificateData,
  objectName,
  pod,
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const generatedCertificate = useSelector(generatedCertificateSelectors.get);
  const generatingCertificate = useSelector(
    generatedCertificateSelectors.loading
  );
  const podErrors = useSelector(podSelectors.errors);
  const podSaved = useSelector(podSelectors.saved);
  const podSaving = useSelector(podSelectors.saving);
  const [shouldGenerateCert, setShouldGenerateCert] = useState(true);

  useEffect(() => {
    return () => {
      dispatch(generalActions.clearGeneratedCertificate());
      dispatch(podActions.cleanup());
    };
  }, [dispatch]);

  const UpdateCertificateSchema = Yup.object().shape({
    certificate: shouldGenerateCert
      ? Yup.string()
      : Yup.string().required("Certificate is required"),
    key: shouldGenerateCert
      ? Yup.string()
      : Yup.string().required("Private key is required"),
    password: Yup.string(),
  });

  let onCancel: FormikFormProps<UpdateCertificateValues>["onCancel"];
  if (hasCertificateData) {
    // Pods created after MAAS 3.1.0 will already have certificate data, so
    // can close the form on cancel.
    onCancel = () => {
      closeForm();
    };
  } else if (generatedCertificate) {
    // Otherwise, if a certificate has already been generated, take the user
    // back to the generate certificate step on cancel.
    onCancel = () => dispatch(generalActions.clearGeneratedCertificate());
  } else {
    // Otherwise, the user should already be on the generated certificate step
    // so there should not be cancel button.
    onCancel = null;
  }

  return (
    <FormikForm<UpdateCertificateValues>
      allowAllEmpty={shouldGenerateCert}
      allowUnchanged={shouldGenerateCert}
      aria-label="Update certificate"
      errors={podErrors}
      initialValues={{ certificate: "", key: "", password: "" }}
      onCancel={onCancel}
      onSubmit={(values) => {
        if (generatedCertificate) {
          dispatch(
            podActions.update({
              certificate: generatedCertificate.certificate,
              id: pod.id,
              key: generatedCertificate.private_key,
              password: values.password,
              tags: pod.tags.join(","),
            })
          );
        } else if (shouldGenerateCert) {
          dispatch(
            generalActions.generateCertificate({
              object_name: objectName || pod.name,
            })
          );
        } else {
          dispatch(
            podActions.update({
              certificate: values.certificate,
              id: pod.id,
              key: values.key,
              tags: pod.tags.join(","),
            })
          );
        }
      }}
      onSuccess={closeForm}
      saved={podSaved}
      saving={generatingCertificate || podSaving}
      submitLabel={
        shouldGenerateCert && !generatedCertificate ? "Next" : "Save"
      }
      validationSchema={UpdateCertificateSchema}
    >
      <UpdateCertificateFields
        generatedCertificate={generatedCertificate}
        setShouldGenerateCert={setShouldGenerateCert}
        shouldGenerateCert={shouldGenerateCert}
      />
    </FormikForm>
  );
};

export default UpdateCertificate;
