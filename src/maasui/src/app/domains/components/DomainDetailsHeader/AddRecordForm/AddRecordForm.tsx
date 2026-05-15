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
import { RecordType } from "@/app/store/domain/types";
import { isAddressRecord } from "@/app/store/domain/utils";

export enum Labels {
  SubmitLabel = "Add record",
}

type Props = {
  id: Domain["id"];
};

type CreateRecordValues = {
  name: DomainResource["name"];
  rrtype: DomainResource["rrtype"];
  rrdata: DomainResource["rrdata"];
  ttl: DomainResource["ttl"] | "";
};

const CreateRecordSchema: SchemaOf<CreateRecordValues> = Yup.object()
  .shape({
    name: Yup.string().required("Name is required."),
    rrtype: Yup.string().required("Record type is required."),
    rrdata: Yup.string().required("Record data is required."),
    ttl: Yup.number().min(
      MIN_TTL,
      "Ensure this value is greater than or equal to 1."
    ),
  })
  .defined();

const AddRecordForm = ({ id }: Props): React.ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const errors = useSelector(domainSelectors.errors);
  const saved = useSelector(domainSelectors.saved);
  const saving = useSelector(domainSelectors.saving);
  const cleanup = useCallback(() => domainActions.cleanup(), []);

  return (
    <FormikForm<CreateRecordValues>
      cleanup={cleanup}
      errors={errors}
      initialValues={{
        name: "",
        rrtype: RecordType.A,
        rrdata: "",
        ttl: "",
      }}
      onCancel={closeSidePanel}
      onSubmit={(values) => {
        dispatch(cleanup());
        if (isAddressRecord(values.rrtype)) {
          const params = {
            address_ttl: Number(values.ttl) || null,
            domain: id,
            ip_addresses: (values.rrdata ?? "").split(/[ ,]+/),
            name: values.name,
          };
          dispatch(domainActions.createAddressRecord(params));
        } else {
          const params = {
            domain: id,
            name: values.name,
            rrdata: values.rrdata,
            rrtype: values.rrtype,
            ttl: Number(values.ttl) || null,
          };
          dispatch(domainActions.createDNSData(params));
        }
      }}
      onSuccess={() => {
        closeSidePanel();
      }}
      saved={saved}
      saving={saving}
      submitLabel={Labels.SubmitLabel}
      validationSchema={CreateRecordSchema}
    >
      <RecordFields />
    </FormikForm>
  );
};

export default AddRecordForm;
