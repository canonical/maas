import { useCallback } from "react";

import { Col, Row } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import { useGetIsSuperUser } from "@/app/api/query/auth";
import Definition from "@/app/base/components/Definition";
import EditableSection from "@/app/base/components/EditableSection";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { domainActions } from "@/app/store/domain";
import { MIN_TTL } from "@/app/store/domain/constants";
import domainsSelectors from "@/app/store/domain/selectors";
import type { Domain } from "@/app/store/domain/types";
import type { RootState } from "@/app/store/root/types";

const EditDomainSchema = Yup.object().shape({
  authoritative: Yup.boolean(),
  name: Yup.string().required("Name is required."),
  ttl: Yup.number().min(MIN_TTL, "TTL must be greater than 1."),
});

export enum Labels {
  Title = "Domain summary",
  Summary = "Domain summary details",
  FormLabel = "Edit domain",
  SubmitLabel = "Save",
  Name = "Name",
  Ttl = "TTL",
  Authoritative = "Authoritative",
}

type EditDomainValues = {
  authoritative: Domain["authoritative"];
  name: Domain["name"];
  ttl: Domain["ttl"] | "";
};

type Props = {
  id: Domain["id"];
};

const DomainSummary = ({ id }: Props): React.ReactElement | null => {
  const dispatch = useDispatch();
  const domain = useSelector((state: RootState) =>
    domainsSelectors.getById(state, id)
  );
  const errors = useSelector(domainsSelectors.errors);
  const saved = useSelector(domainsSelectors.saved);
  const saving = useSelector(domainsSelectors.saving);
  const cleanup = useCallback(() => domainActions.cleanup(), []);

  const isSuperUser = useGetIsSuperUser();

  if (!domain) {
    return null;
  }

  return (
    <EditableSection
      canEdit={isSuperUser.data}
      hasSidebarTitle
      renderContent={(editing, setEditing) =>
        editing ? (
          <FormikForm<EditDomainValues>
            aria-label={Labels.FormLabel}
            cleanup={cleanup}
            data-testid="domain-summary-form"
            errors={errors}
            initialValues={{
              authoritative: domain.authoritative,
              name: domain.name || "",
              ttl: domain.ttl || "",
            }}
            onCancel={() => {
              setEditing(false);
            }}
            onSubmit={(values) => {
              dispatch(cleanup());
              dispatch(
                domainActions.update({
                  authoritative: values.authoritative,
                  id: domain.id,
                  name: values.name,
                  ttl: values.ttl || null,
                })
              );
            }}
            onSuccess={() => {
              setEditing(false);
            }}
            saved={saved}
            saving={saving}
            submitLabel={Labels.SubmitLabel}
            validationSchema={EditDomainSchema}
          >
            <Row>
              <Col size={6}>
                <FormikField
                  label={Labels.Name}
                  name="name"
                  placeholder={Labels.Name}
                  required
                  type="text"
                />
              </Col>
              <Col size={6}>
                <FormikField
                  label={Labels.Ttl}
                  min={MIN_TTL}
                  name="ttl"
                  type="number"
                />
              </Col>
            </Row>
            <Row>
              <Col size={6}>
                <FormikField
                  label={Labels.Authoritative}
                  name="authoritative"
                  type="checkbox"
                />
              </Col>
            </Row>
          </FormikForm>
        ) : (
          <Row aria-label={Labels.Summary} data-testid="domain-summary">
            <Col size={6}>
              <Definition label={Labels.Name}>{domain.name}</Definition>
              <Definition label={Labels.Ttl}>
                {domain.ttl || "(default)"}
              </Definition>
              <Definition label={Labels.Authoritative}>
                {domain.authoritative ? "Yes" : "No"}
              </Definition>
            </Col>
          </Row>
        )
      }
      title={Labels.Title}
    />
  );
};

export default DomainSummary;
