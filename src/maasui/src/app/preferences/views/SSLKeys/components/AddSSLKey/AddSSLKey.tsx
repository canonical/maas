import type { ReactElement } from "react";

import type { TextareaProps } from "@canonical/react-components";
import { Col, Row, Textarea } from "@canonical/react-components";
import * as Yup from "yup";

import { useCreateSslKeys } from "@/app/api/query/sslKeys";
import type { CreateUserSslkeyError, SslKeyRequest } from "@/app/apiclient";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";

// This can be removed when the autoComplete prop is supported:
// https://github.com/canonical/react-components/issues/571
const ProxyTextarea = (
  props: TextareaProps & { autoComplete?: "off" | "on" }
) => <Textarea {...props} />;

const SSLKeySchema = Yup.object().shape({
  key: Yup.string().required("SSL key is required"),
});

export const AddSSLKey = (): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const uploadSslKey = useCreateSslKeys();

  return (
    <FormikForm<SslKeyRequest, CreateUserSslkeyError>
      aria-label="Add SSL key"
      errors={uploadSslKey.error}
      initialValues={{ key: "" }}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Saved",
        category: "SSL keys preferences",
        label: "Add SSL key form",
      }}
      onSubmit={(values) => {
        if (values.key && values.key !== "") {
          uploadSslKey.mutate({
            body: {
              key: values.key,
            },
          });
        }
      }}
      onSuccess={closeSidePanel}
      resetOnSave={true}
      saved={uploadSslKey.isSuccess}
      saving={uploadSslKey.isPending}
      submitLabel="Save SSL key"
      validationSchema={SSLKeySchema}
    >
      <Row>
        <Col size={12}>
          <FormikField
            autoCapitalize="off"
            autoComplete="off"
            autoCorrect="off"
            className="ssl-key-form-fields__key p-text--code"
            component={ProxyTextarea}
            label="SSL key"
            name="key"
            spellCheck="false"
          />
        </Col>
        <Col size={12}>
          <p className="form-card__help">
            You will be able to access Windows winrm service with a registered
            key.
          </p>
        </Col>
      </Row>
    </FormikForm>
  );
};

export default AddSSLKey;
