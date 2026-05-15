import { useCallback } from "react";

import { Icon } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import urls from "@/app/base/urls";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";
import type { Domain } from "@/app/store/domain/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  id: Domain["id"];
};

export enum Labels {
  DeleteLabel = "Delete domain",
  AreYouSure = "Are you sure you want to delete this domain?",
  CannotDelete = "Domain cannot be deleted because it has resource records. Remove all resource records from the domain to allow deletion.",
}

const DeleteDomainForm = ({ id }: Props): React.ReactElement | null => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const domain = useSelector((state: RootState) =>
    domainSelectors.getById(state, id)
  );
  const errors = useSelector(domainSelectors.errors);
  const saved = useSelector(domainSelectors.saved);
  const saving = useSelector(domainSelectors.saving);
  const cleanup = useCallback(() => domainActions.cleanup(), []);

  if (!domain) {
    return null;
  }

  const canBeDeleted = domain.resource_count === 0;
  let message = Labels.AreYouSure;
  if (!canBeDeleted) {
    message = Labels.CannotDelete;
  }

  return (
    <FormikForm<EmptyObject>
      cleanup={cleanup}
      errors={errors}
      initialValues={{}}
      onCancel={closeSidePanel}
      onSubmit={() => {
        dispatch(cleanup());
        dispatch(domainActions.delete(id));
      }}
      saved={saved}
      savedRedirect={urls.domains.index}
      saving={saving}
      submitAppearance="negative"
      submitDisabled={!canBeDeleted}
      submitLabel={Labels.DeleteLabel}
    >
      <p
        className="u-no-margin--bottom u-no-max-width"
        data-testid="delete-message"
      >
        <Icon className="is-inline" name="error" />
        {message}
      </p>
    </FormikForm>
  );
};

export default DeleteDomainForm;
