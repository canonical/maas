import { useCallback } from "react";

import { Icon } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";
import type { Domain, DomainResource } from "@/app/store/domain/types";
import { isDomainDetails } from "@/app/store/domain/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  id: Domain["id"];
  resource: DomainResource;
};

export const Labels = {
  FormLabel: "Remove record",
  SubmitLabel: "Remove record",
  AreYouSure: "Are you sure you want to remove this record?",
} as const;

const DeleteRecordForm = ({
  id,
  resource,
}: Props): React.ReactElement | null => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const domain = useSelector((state: RootState) =>
    domainSelectors.getById(state, id)
  );
  const errors = useSelector(domainSelectors.errors);
  const saved = useSelector(domainSelectors.saved);
  const saving = useSelector(domainSelectors.saving);
  const cleanup = useCallback(() => domainActions.cleanup(), []);

  if (!isDomainDetails(domain)) {
    return null;
  }

  const hasMultipleRecords =
    domain.rrsets.filter(
      (rrset) => rrset.dnsresource_id === resource.dnsresource_id
    ).length > 1;

  return (
    <FormikForm<EmptyObject>
      aria-label={Labels.FormLabel}
      cleanup={cleanup}
      errors={errors}
      initialValues={{}}
      onCancel={closeSidePanel}
      onSubmit={() => {
        dispatch(cleanup());
        const params = {
          deleteResource: !hasMultipleRecords,
          domain: id,
          rrset: resource,
        };
        dispatch(domainActions.deleteRecord(params));
      }}
      onSuccess={closeSidePanel}
      saved={saved}
      saving={saving}
      submitAppearance="negative"
      submitLabel={Labels.SubmitLabel}
    >
      <p
        className="u-no-margin--bottom u-no-max-width"
        data-testid="delete-message"
      >
        <Icon className="is-inline" name="error" />
        {Labels.AreYouSure}
      </p>
    </FormikForm>
  );
};

export default DeleteRecordForm;
