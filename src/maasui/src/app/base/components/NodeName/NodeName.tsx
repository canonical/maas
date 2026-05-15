import { useEffect, useState } from "react";

import { Button, Spinner } from "@canonical/react-components";
import { usePrevious } from "@canonical/react-components/dist/hooks";
import type { FormikErrors } from "formik";
import * as Yup from "yup";

import NodeNameFields from "./NodeNameFields";

import FormikForm from "@/app/base/components/FormikForm";
import { useCanEdit } from "@/app/base/hooks";
import { hostnameValidation } from "@/app/base/validation";
import type { Domain, DomainMeta } from "@/app/store/domain/types";
import type { Node, SimpleNode } from "@/app/store/types/node";
import { nodeIsController } from "@/app/store/utils";

export type Props = {
  editingName: boolean;
  // Machines and devices can edit their name, but no controllers.
  node: Node | null;
  onSubmit: (
    hostname: SimpleNode["hostname"],
    domain: Domain[DomainMeta.PK]
  ) => void;
  setEditingName: (editingName: boolean) => void;
  saved?: boolean;
  saving?: boolean;
};

export type FormValues = {
  hostname: string;
  domain: string;
};

const Schema = Yup.object().shape({
  hostname: hostnameValidation.required(),
  domain: Yup.string(),
});

const NodeName = ({
  editingName,
  node,
  onSubmit,
  setEditingName,
  saved,
  saving,
}: Props): React.ReactElement => {
  const [hostnameError, setHostnameError] = useState<
    FormikErrors<FormValues>["hostname"] | null
  >(null);
  const canEdit = useCanEdit(node);
  const previousSaving = usePrevious(saving);
  const canEditHostname = !nodeIsController(node);

  useEffect(() => {
    // The node has transitioned from saving to saved so close the form.
    if (saved && !saving && previousSaving) {
      setEditingName(false);
    }
  }, [previousSaving, saved, saving, setEditingName]);

  if (!node) {
    return <Spinner />;
  }
  if (!canEdit) {
    return <span className="node-name">{node.fqdn}</span>;
  }
  if (!editingName) {
    return (
      <Button
        appearance="base"
        className="node-name--editable"
        onClick={() => {
          setEditingName(true);
        }}
      >
        {node.fqdn}
      </Button>
    );
  }
  return (
    <FormikForm<FormValues>
      className="node-name"
      footer={
        hostnameError ? (
          <div className="node-name__error is-error">
            <p className="p-form-validation__message u-no-margin--bottom">
              <strong>Error:</strong> {hostnameError}
            </p>
          </div>
        ) : null
      }
      initialValues={{
        domain: String(node.domain.id),
        hostname: node.hostname,
      }}
      inline
      onCancel={() => {
        setEditingName(false);
      }}
      onSaveAnalytics={{
        action: "Saved",
        category: "Node details header",
        label: "name",
      }}
      onSubmit={({ hostname, domain }) => {
        onSubmit(hostname, Number(domain));
      }}
      saved={saved}
      saving={saving}
      validationSchema={Schema}
    >
      <NodeNameFields
        canEditHostname={canEditHostname}
        saving={saving}
        setHostnameError={setHostnameError}
      />
    </FormikForm>
  );
};

export default NodeName;
