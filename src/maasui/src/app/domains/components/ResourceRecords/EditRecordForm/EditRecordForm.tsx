import { useCallback } from "react";

import { useDispatch, useSelector } from "react-redux";
import type { SchemaOf } from "yup";
import * as Yup from "yup";

import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { RecordFields } from "@/app/domains/components";
import { domainActions } from "@/app/store/domain";
import { MIN_TTL } from "@/app/store/domain/constants";
import domainSelectors from "@/app/store/domain/selectors";
import type { Domain, DomainResource } from "@/app/store/domain/types";

type Props = {
  id: Domain["id"];
  resource: DomainResource;
};

export enum Labels {
  FormLabel = "Edit record",
  SubmitLabel = "Save record",
}

export type EditRecordValues = {
  name: DomainResource["name"];
  rrdata: DomainResource["rrdata"];
  rrtype: DomainResource["rrtype"];
  ttl: DomainResource["ttl"] | "";
};

const EditRecordSchema: SchemaOf<EditRecordValues> = Yup.object()
  .shape({
    name: Yup.string().required("Name is required."),
    rrtype: Yup.string().required("Record type is required."),
    rrdata: Yup.string().required("Record data is required."),
    ttl: Yup.number().min(MIN_TTL, "TTL must be greater than 1."),
  })
  .defined();

const EditRecordForm = ({ id, resource }: Props): React.ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const errors = useSelector(domainSelectors.errors);
  const saved = useSelector(domainSelectors.saved);
  const saving = useSelector(domainSelectors.saving);
  const cleanup = useCallback(() => domainActions.cleanup(), []);

  return (
    <FormikForm<EditRecordValues>
      aria-label={Labels.FormLabel}
      cleanup={cleanup}
      errors={errors}
      initialValues={{
        name: resource.name || "",
        rrtype: resource.rrtype,
        rrdata: resource.rrdata || "",
        ttl: resource.ttl || "",
      }}
      onCancel={closeSidePanel}
      onSubmit={(values) => {
        dispatch(cleanup());
        const params = {
          domain: id,
          name: values.name,
          rrset: resource,
          rrdata: values.rrdata,
          ttl: Number(values.ttl) || null,
        };
        dispatch(domainActions.updateRecord(params));
      }}
      onSuccess={closeSidePanel}
      saved={saved}
      saving={saving}
      submitDisabled={false}
      submitLabel={Labels.SubmitLabel}
      validationSchema={EditRecordSchema}
    >
      <RecordFields editing />
    </FormikForm>
  );
};

export default EditRecordForm;
