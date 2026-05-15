import type { ReactNode } from "react";

import type {
  ButtonAppearance,
  ButtonProps,
  ContextualMenuDropdownProps,
  ValueOf,
} from "@canonical/react-components";
import { ContextualMenu, Tooltip } from "@canonical/react-components";

import type { DataTestElement } from "@/app/base/types";
import type { Node } from "@/app/store/types/node";
import { NodeActions } from "@/app/store/types/node";
import { canOpenActionForm, getNodeActionTitle } from "@/app/store/utils";

export enum Label {
  TakeAction = "Take action",
}

type ActionGroup = {
  actions: NodeActions[];
  name: string;
};

type ActionLink = DataTestElement<ButtonProps>;

type Props = Pick<ContextualMenuDropdownProps, "constrainPanelWidth"> & {
  alwaysShowLifecycle?: boolean;
  className?: string;
  disabledTooltipPosition?: "left" | "top-left";
  excludeActions?: NodeActions[];
  filterActions?: boolean;
  getTitle?: (action: NodeActions) => ReactNode | null;
  hasSelection: boolean;
  menuPosition?: "left" | "right";
  nodeDisplay?: string;
  nodes?: Node[];
  onActionClick: (action: NodeActions) => void;
  showCount?: boolean;
  toggleAppearance?: ValueOf<typeof ButtonAppearance>;
  toggleClassName?: string | null;
  toggleLabel?: string;
};

const actionGroups: ActionGroup[] = [
  {
    name: "lifecycle",
    actions: [
      NodeActions.COMMISSION,
      NodeActions.ACQUIRE,
      NodeActions.DEPLOY,
      NodeActions.RELEASE,
      NodeActions.ABORT,
      NodeActions.CLONE,
    ],
  },
  {
    name: "power",
    actions: [
      NodeActions.ON,
      NodeActions.OFF,
      NodeActions.SOFT_OFF,
      NodeActions.CHECK_POWER,
    ],
  },
  {
    name: "testing",
    actions: [
      NodeActions.TEST,
      NodeActions.RESCUE_MODE,
      NodeActions.EXIT_RESCUE_MODE,
      NodeActions.MARK_FIXED,
      NodeActions.MARK_BROKEN,
      NodeActions.OVERRIDE_FAILED_TESTING,
    ],
  },
  {
    name: "lock",
    actions: [NodeActions.LOCK, NodeActions.UNLOCK],
  },
  {
    name: "misc",
    actions: [
      NodeActions.TAG,
      NodeActions.SET_ZONE,
      NodeActions.SET_POOL,
      NodeActions.IMPORT_IMAGES,
      NodeActions.DELETE,
    ],
  },
];

const getTakeActionLinks = (
  onActionClick: (action: NodeActions) => void,
  excludeActions: NodeActions[],
  alwaysShowLifecycle: boolean,
  showCount?: boolean,
  filterActions?: boolean,
  getTitle?: Props["getTitle"],
  nodes?: Node[]
) => {
  return actionGroups.reduce<ActionLink[][]>((links, group) => {
    const groupLinks = group.actions.reduce<ActionLink[]>(
      (groupLinks, action) => {
        if (excludeActions.includes(action)) {
          return groupLinks;
        }

        // Only show "Power cycle" if the feature flag is enabled.
        // TODO: Remove DPU provisioning feature flag https://warthogs.atlassian.net/browse/MAASENG-4186
        if (
          action === NodeActions.POWER_CYCLE &&
          import.meta.env.VITE_APP_DPU_PROVISIONING !== "true"
        ) {
          return groupLinks;
        }

        // When nodes are not provided then counts should not be visible.
        const count =
          nodes?.reduce(
            (sum, node) => (canOpenActionForm(node, action) ? sum + 1 : sum),
            0
          ) ?? 0;
        // If alwaysShowLifecycle is true, we display lifecycle actions
        // regardless of whether any of the provided nodes can perform them.
        // Otherwise, the action is not rendered.
        if (
          (filterActions &&
            (count > 0 ||
              (group.name === "lifecycle" && alwaysShowLifecycle))) ||
          // When there are no counts the actions should always be visible.
          !filterActions
        ) {
          groupLinks.push({
            children: (
              <div className="u-flex--between">
                <span>
                  {getTitle?.(action) ?? getNodeActionTitle(action)}
                  ...
                </span>
                {showCount && (
                  <span
                    className="u-nudge-right--small"
                    data-testid={`action-count-${action}`}
                  >
                    {count || ""}
                  </span>
                )}
              </div>
            ),
            "data-testid": `action-link-${action}`,
            // When nodes are not provided actions should always be enabled.
            disabled: nodes ? count === 0 : false,
            onClick: () => {
              onActionClick(action);
            },
          });
        }
        return groupLinks;
      },
      []
    );

    if (groupLinks.length > 0) {
      links.push(groupLinks);
    }
    return links;
  }, []);
};

export const NodeActionMenu = ({
  alwaysShowLifecycle = false,
  className,
  disabledTooltipPosition = "left",
  excludeActions = [],
  filterActions,
  getTitle,
  hasSelection,
  menuPosition = "right",
  nodeDisplay = "node",
  nodes,
  onActionClick,
  showCount,
  toggleAppearance = "positive",
  toggleClassName,
  toggleLabel = Label.TakeAction,
  constrainPanelWidth,
}: Props): React.ReactElement => {
  return (
    <Tooltip
      message={
        !hasSelection
          ? `Select ${nodeDisplay}s below to perform an action.`
          : null
      }
      position={disabledTooltipPosition}
    >
      <ContextualMenu
        className={className}
        constrainPanelWidth={constrainPanelWidth}
        data-testid="take-action-dropdown"
        hasToggleIcon
        links={getTakeActionLinks(
          onActionClick,
          excludeActions,
          alwaysShowLifecycle,
          showCount,
          filterActions,
          getTitle,
          nodes
        )}
        position={menuPosition}
        toggleAppearance={toggleAppearance}
        toggleClassName={toggleClassName}
        toggleDisabled={!hasSelection}
        toggleLabel={toggleLabel}
      />
    </Tooltip>
  );
};

export default NodeActionMenu;
