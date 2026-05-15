import { useEffect, useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type { ValueOf } from "@canonical/react-components";
import { Button } from "@canonical/react-components";
import pluralize from "pluralize";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import type { APIError, SetSearchFilter } from "@/app/base/types";
import urls from "@/app/base/urls";
import useCloneResultsColumns from "@/app/machines/components/MachineForms/MachineActionFormWrapper/CloneForm/CloneResults/useCloneResultsColumns/useCloneResultsColumns";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine, MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import { formatErrors } from "@/app/utils";

import "./_index.scss";

export const CloneErrorCodes = {
  IS_SOURCE: "is-source",
  ITEM_INVALID: "item_invalid",
  NETWORKING: "networking",
  STORAGE: "storage",
} as const;

export type CloneError = {
  destinations: {
    code: ValueOf<typeof CloneErrorCodes>;
    message: string;
    system_id?: Machine["system_id"];
  }[];
};

export type FormattedCloneError = {
  id: number;
  code: ValueOf<typeof CloneErrorCodes> | "global";
  description: string;
  destinations: Machine["system_id"][];
};

type Props = {
  closeForm: () => void;
  // This is optional because it can show in a machine's details page.
  setSearchFilter?: SetSearchFilter;
  selectedCount?: number | null;
  sourceMachine: MachineDetails | null;
  viewingDetails?: boolean;
};

const getErrorDescription = (code: ValueOf<typeof CloneErrorCodes>) => {
  // TODO: Update with more specific error messages.
  // https://github.com/canonical/maas-ui/issues/3009
  switch (code) {
    case CloneErrorCodes.IS_SOURCE:
      return "Source machine cannot be a destination machine.";
    case CloneErrorCodes.ITEM_INVALID:
      return "Cloning aborted due to the following invalid destinations:";
    case CloneErrorCodes.NETWORKING:
      return "Source networking does not match destination networking.";
    case CloneErrorCodes.STORAGE:
      return "Source storage does not match destination storage.";
    default:
      return "Cloning was unsuccessful.";
  }
};

const getSystemId = (error: CloneError["destinations"][0]) => {
  if ("system_id" in error && typeof error.system_id === "string") {
    return error.system_id;
  } else if (error.code === CloneErrorCodes.ITEM_INVALID) {
    // Item invalid errors short circuit the clone operation, and the API is
    // unable to send through a system_id without some significant reworking of
    // how the Django forms work. For this case we extract the system_id from
    // the error message manually.
    return (
      /Machine [0-9]+ is invalid: Select a valid choice\. (.{6}) is not one of the available choices\./.exec(
        error.message
      )?.[1] || ""
    );
  }
  return "";
};

const formatCloneError = (
  error: APIError<CloneError>
): FormattedCloneError[] => {
  if (!error) {
    return [];
  } else if (typeof error === "object" && "destinations" in error) {
    const cloneError = error as CloneError;
    return cloneError.destinations.reduce<FormattedCloneError[]>(
      (formattedErrors, error, currentIndex) => {
        const existingError = formattedErrors.find(
          (formattedError) => formattedError.code === error.code
        );
        const systemId = getSystemId(error);
        if (existingError) {
          existingError.destinations.push(systemId);
          return formattedErrors;
        } else {
          formattedErrors.push({
            id: currentIndex,
            code: error.code,
            description: getErrorDescription(error.code),
            destinations: [systemId],
          });
        }
        return formattedErrors;
      },
      []
    );
  }
  // If an error is returned and it's not tied to the selected destinations,
  // assume the error is global and therefore no machines were cloned to
  // successfully.
  return [
    {
      id: 1,
      code: "global",
      description: `Cloning was unsuccessful: ${formatErrors(error)}`,
      destinations: [],
    },
  ];
};

export const CloneResults = ({
  closeForm,
  selectedCount,
  setSearchFilter,
  sourceMachine,
  viewingDetails,
}: Props): React.ReactElement | null => {
  const [destinationCount, setDestinationCount] = useState(0);
  const cloneErrors = useSelector((state: RootState) =>
    machineSelectors.eventErrorsForIds(
      state,
      sourceMachine?.system_id || "",
      NodeActions.CLONE
    )
  );

  useEffect(() => {
    // We set destination count in local state otherwise the user could unselect
    // machines and change the results.
    if (!destinationCount && selectedCount) {
      setDestinationCount(selectedCount);
    }
  }, [destinationCount, selectedCount]);

  const apiError: APIError<CloneError> = cloneErrors.length
    ? cloneErrors[0].error
    : null;
  const formattedCloneErrors = formatCloneError(apiError);
  // Item invalid errors short circuit the clone operation, so even though only
  // a subset of destination return an item invalid error, none of the
  // destinations actually get cloned to.
  const failedCount = formattedCloneErrors.some(
    (error) =>
      error.code === CloneErrorCodes.ITEM_INVALID ||
      error.destinations.length === 0
  )
    ? destinationCount
    : formattedCloneErrors.reduce<Machine["system_id"][]>(
        (failedIds, error) => {
          error.destinations.forEach((destId) => {
            if (!failedIds.includes(destId)) {
              failedIds.push(destId);
            }
          });
          return failedIds;
        },
        []
      ).length;

  const columns = useCloneResultsColumns({
    failedCount,
    setSearchFilter,
  });

  if (!sourceMachine) {
    return null;
  }

  return (
    <>
      <div className="clone-results">
        <h5 className="clone-results__title p-heading--5">Cloning complete</h5>
        <div className="clone-results__info">
          <p data-testid="results-string">
            {`${destinationCount - failedCount} of ${pluralize(
              "machine",
              destinationCount,
              true
            )} cloned successfully from `}
            <Link
              to={urls.machines.machine.index({ id: sourceMachine.system_id })}
            >
              {sourceMachine.hostname}
            </Link>
            .
          </p>
          {formattedCloneErrors.length > 0 && (
            <>
              <p>The following errors occurred:</p>
              <GenericTable
                className="clone-results-table"
                columns={columns}
                data={formattedCloneErrors}
                data-testid="errors-table"
                filterCells={(_, column) =>
                  viewingDetails
                    ? !["affectedMachines"].includes(column.id)
                    : true
                }
                filterHeaders={(header) =>
                  viewingDetails
                    ? !["affectedMachines"].includes(header.id)
                    : true
                }
                isLoading={false}
              />
            </>
          )}
        </div>
      </div>
      <hr />
      <div className="u-align--right">
        <Button appearance="base" onClick={closeForm}>
          Close
        </Button>
      </div>
    </>
  );
};

export default CloneResults;
