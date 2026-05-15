import { useEffect } from "react";

import { Spinner } from "@canonical/react-components";
import type { FormikErrors } from "formik";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { FormValues } from "../NodeName";

import DomainSelect from "@/app/base/components/DomainSelect";
import FormikField from "@/app/base/components/FormikField";
import domainSelectors from "@/app/store/domain/selectors";
import { DomainMeta } from "@/app/store/domain/types";

type Props = {
  canEditHostname?: boolean;
  saving?: boolean;
  setHostnameError: (
    error: FormikErrors<FormValues>["hostname"] | null
  ) => void;
};

const NodeHostnameField = ({
  saving,
  setHostnameError,
}: Props): React.ReactElement => {
  const { errors, values } = useFormikContext<FormValues>();
  const hostnameError = errors.hostname;

  useEffect(() => {
    setHostnameError(hostnameError ?? null);
  }, [hostnameError, setHostnameError]);

  return (
    <div className="node-name__hostname-wrapper u-no-margin--right">
      <div aria-hidden="true" className="node-name__hostname-spacer">
        {values.hostname}
      </div>
      <FormikField
        className="node-name__hostname"
        disabled={saving}
        displayError={false}
        label="Hostname"
        name="hostname"
        takeFocus
        type="text"
        wrapperClassName="u-no-margin--right"
      />
    </div>
  );
};

const NodeDomainField = ({
  saving,
}: Pick<Props, "saving">): React.ReactElement => {
  const domainsLoaded = useSelector(domainSelectors.loaded);

  return domainsLoaded ? (
    <DomainSelect
      className="u-no-margin--bottom"
      disabled={saving}
      label="Domain"
      name="domain"
      valueKey={DomainMeta.PK}
      wrapperClassName="node-name__domain"
    />
  ) : (
    <Spinner className="u-width--auto" />
  );
};

const NodeNameFields = ({
  canEditHostname,
  setHostnameError,
  saving,
}: Props): React.ReactElement => {
  const { values } = useFormikContext<FormValues>();

  return (
    <>
      {canEditHostname ? (
        <NodeHostnameField
          canEditHostname={canEditHostname}
          saving={saving}
          setHostnameError={setHostnameError}
        />
      ) : (
        <div className="node-name__hostname--no-edit">
          <span className="node-name">{values.hostname}</span>
        </div>
      )}
      <span className="node-name__dot u-nudge-right--small u-nudge-left--small u-no-margin--right">
        .
      </span>
      <NodeDomainField saving={saving} />
    </>
  );
};

export default NodeNameFields;
