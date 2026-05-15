import type { ReactElement } from "react";

import pluralize from "pluralize";

import MachineHostname from "../MachineHostname";

import type { ActionState } from "@/app/base/types";

const ErrorDetailsItem = ({
  errorMessage,
  systemIds,
}: {
  errorMessage: keyof NonNullable<ActionState["failureDetails"]>;
  systemIds: ActionState["failedSystemIds"];
}) => {
  return (
    <dl className="u-no-margin--bottom">
      <dt>{errorMessage}</dt>
      {systemIds?.map((systemId) => (
        <dd key={systemId}>
          <MachineHostname systemId={systemId} />
        </dd>
      ))}
    </dl>
  );
};

const ErrorDetailsList = ({
  failureDetails,
}: {
  failureDetails: NonNullable<ActionState["failureDetails"]>;
}): React.ReactElement => {
  return (
    <>
      {Object.keys(failureDetails).length > 0
        ? Object.entries(failureDetails).map(
            ([errorMessage, systemIds], index) => (
              <ErrorDetailsItem
                errorMessage={errorMessage}
                key={`${errorMessage}-${index}`}
                systemIds={systemIds}
              />
            )
          )
        : null}
    </>
  );
};

const ErrorDetails = ({
  failureDetails,
  failedSystemIds,
}: Pick<
  ActionState,
  "failedSystemIds" | "failureDetails"
>): ReactElement | null => {
  const failedSystemIdsCount = failedSystemIds?.length ?? 0;

  return failedSystemIdsCount > 0 ? (
    <>
      <div>
        Action failed for {pluralize("machine", failedSystemIdsCount, true)}.
      </div>
      {failureDetails ? (
        <ErrorDetailsList failureDetails={failureDetails} />
      ) : null}
    </>
  ) : null;
};

export default ErrorDetails;
