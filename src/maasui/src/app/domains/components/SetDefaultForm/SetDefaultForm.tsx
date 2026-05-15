import type { ReactElement } from "react";

import { useDispatch, useSelector } from "react-redux";

import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { Labels } from "@/app/domains/components/DomainsTable/DomainsTable";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";
import type { Domain, DomainMeta } from "@/app/store/domain/types";

type Props = {
  id: Domain[DomainMeta.PK];
};
const SetDefaultForm = ({ id }: Props): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const errors = useSelector(domainSelectors.errors);
  const saving = useSelector(domainSelectors.saving);
  const saved = useSelector(domainSelectors.saved);
  return (
    <ModelActionForm
      aria-label={Labels.FormTitle}
      errors={errors}
      initialValues={{}}
      message={Labels.AreYouSure}
      modelType="DNS"
      onCancel={() => {
        dispatch(domainActions.cleanup());
        closeSidePanel();
      }}
      onSubmit={() => {
        dispatch(domainActions.setDefault(id));
      }}
      onSuccess={() => {
        dispatch(domainActions.cleanup());
        closeSidePanel();
      }}
      saved={saved}
      saving={saving}
      submitAppearance="positive"
      submitLabel={Labels.ConfirmSetDefault}
    />
  );
};

export default SetDefaultForm;
