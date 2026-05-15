import { useEffect, useState } from "react";

import { ContentSection, MainToolbar } from "@canonical/maas-react-components";
import { Button, MainTable, Spinner } from "@canonical/react-components";
import classNames from "classnames";
import { useDispatch, useSelector } from "react-redux";
import type { Dispatch } from "redux";

import ScriptDetails from "../ScriptDetails";

import ColumnToggle from "@/app/base/components/ColumnToggle";
import SearchBox from "@/app/base/components/SearchBox";
import TableActions from "@/app/base/components/TableActions";
import TableDeleteConfirm from "@/app/base/components/TableDeleteConfirm";
import { useWindowTitle } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import ScriptsUpload from "@/app/settings/views/Scripts/ScriptsUpload";
import type { RootState } from "@/app/store/root/types";
import { scriptActions } from "@/app/store/script";
import scriptSelectors from "@/app/store/script/selectors";
import type { Script } from "@/app/store/script/types";
import { generateEmptyStateMsg, getTableStatus } from "@/app/utils";
import { formatUtcDatetime } from "@/app/utils/time";

export enum Labels {
  Actions = "Table actions",
  DeleteConfirm = "Confirm or cancel script deletion",
  EmptyList = "No scripts available.",
  Loading = "Loading...",
  NoResults = "No scripts match the search criteria.",
}

type Props = {
  type?: "commissioning" | "deployment" | "testing";
};

const generateRows = (
  scripts: Script[],
  expandedId: Script["id"] | null,
  setExpandedId: (id: Script["id"] | null) => void,
  expandedType: "delete" | "details" | null,
  setExpandedType: (expandedType: "delete" | "details") => void,
  hideExpanded: () => void,
  dispatch: Dispatch,
  saved: boolean,
  saving: boolean
) =>
  scripts.map((script) => {
    const expanded = expandedId === script.id;
    const showDelete = expandedType === "delete";
    // history timestamps are in the format: Mon, 02 Sep 2019 02:02:39 -0000
    let uploadedOn: string;
    try {
      uploadedOn = formatUtcDatetime(script.created);
    } catch {
      uploadedOn = "Never";
    }

    return {
      "aria-label": script.name,
      className: expanded ? "p-table__row is-active" : null,
      columns: [
        {
          content: (
            <ColumnToggle
              isExpanded={expanded && !showDelete}
              label={script.name}
              onClose={hideExpanded}
              onOpen={() => {
                setExpandedId(script.id);
                setExpandedType("details");
              }}
            />
          ),
          role: "rowheader",
        },
        {
          content: script.description,
        },
        { content: <span data-testid="upload-date">{uploadedOn}</span> },
        {
          "aria-label": Labels.Actions,
          content: (
            <TableActions
              deleteDisabled={script.default}
              deleteTooltip={
                script.default ? "Default scripts cannot be deleted." : null
              }
              onDelete={() => {
                setExpandedId(script.id);
                setExpandedType("delete");
              }}
            />
          ),
          className: "u-align--right",
        },
      ],
      "data-testid": "script-row",
      expanded: expanded,
      expandedContent:
        expanded &&
        (showDelete ? (
          <div aria-label={Labels.DeleteConfirm}>
            <TableDeleteConfirm
              deleted={saved}
              deleting={saving}
              modelName={script.name}
              modelType="Script"
              onClose={hideExpanded}
              onConfirm={() => {
                dispatch(scriptActions.delete(script.id));
              }}
            />
          </div>
        ) : (
          <ScriptDetails
            id={script.id}
            isCollapsible
            onCollapse={hideExpanded}
          />
        )),
      key: script.id,
      sortData: {
        name: script.name,
        description: script.description,
        uploaded_on: uploadedOn,
      },
    };
  });

const ScriptsList = ({ type = "commissioning" }: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const { openSidePanel } = useSidePanel();
  const [expandedId, setExpandedId] = useState<Script["id"] | null>(null);
  const [expandedType, setExpandedType] = useState<"delete" | "details" | null>(
    null
  );
  const [searchText, setSearchText] = useState("");

  const scriptsLoading = useSelector(scriptSelectors.loading);
  const scriptsLoaded = useSelector(scriptSelectors.loaded);
  const saved = useSelector(scriptSelectors.saved);
  const saving = useSelector(scriptSelectors.saving);

  const userScripts = useSelector((state: RootState) =>
    scriptSelectors.search(state, searchText, type)
  );

  useWindowTitle(`${type[0].toUpperCase()}${type.slice(1)} scripts`);

  const hideExpanded = () => {
    setExpandedId(null);
    setExpandedType(null);
  };

  useEffect(() => {
    if (!scriptsLoaded) {
      // scripts are fetched via http, so we explicitly check if they're already
      // loaded here.
      dispatch(scriptActions.fetch());
    }
  }, [dispatch, scriptsLoaded, type]);

  const tableStatus = getTableStatus({
    isLoading: scriptsLoading,
    hasFilter: !!searchText,
  });

  return (
    <ContentSection>
      <ContentSection.Content>
        <div className="settings-table">
          <MainToolbar>
            <MainToolbar.Title>
              {`${type === "commissioning" ? "Commissioning" : type === "testing" ? "Testing" : "Deployment"} scripts`}
            </MainToolbar.Title>
            <MainToolbar.Controls>
              <SearchBox
                onChange={setSearchText}
                placeholder={`Search ${type} scripts`}
                value={searchText}
              />
              <Button
                onClick={() => {
                  openSidePanel({
                    component: ScriptsUpload,
                    title: `Upload ${type} script`,
                    props: {
                      type,
                    },
                  });
                }}
              >
                Upload script
              </Button>
            </MainToolbar.Controls>
          </MainToolbar>
          {scriptsLoading && (
            <div className="settings-table__loader">
              <Spinner />
            </div>
          )}
          <MainTable
            className={classNames(
              "p-table-expanding u-nudge-down",
              "scripts-list",
              {
                "u-no-padding--bottom": scriptsLoading && !scriptsLoaded,
              }
            )}
            defaultSort="name"
            defaultSortDirection="ascending"
            emptyStateMsg={generateEmptyStateMsg(tableStatus, {
              default: Labels.EmptyList,
              filtered: Labels.NoResults,
            })}
            expanding={true}
            headers={[
              {
                content: "Script name",
                sortKey: "name",
              },
              {
                content: "Description",
                sortKey: "description",
              },
              {
                content: "Uploaded on",
                sortKey: "uploaded_on",
              },
              {
                content: "Actions",
                className: "u-align--right",
              },
            ]}
            paginate={20}
            rows={
              scriptsLoaded
                ? generateRows(
                    userScripts,
                    expandedId,
                    setExpandedId,
                    expandedType,
                    setExpandedType,
                    hideExpanded,
                    dispatch,
                    saved,
                    saving
                  )
                : undefined
            }
            sortable
          />
          {scriptsLoading && !scriptsLoaded && (
            <div className="settings-table__lines"></div>
          )}
        </div>
      </ContentSection.Content>
    </ContentSection>
  );
};

export default ScriptsList;
