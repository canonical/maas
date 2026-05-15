import { Button } from "@canonical/react-components";

import { NodeActions } from "@/app/store/types/node";

const getErrorSentence = (
  action: NodeActions,
  nodeType: string,
  count: number
) => {
  const nodeString = `${count} ${nodeType}${count === 1 ? "" : "s"}`;

  if (count === 0) {
    return `No ${nodeType}s have been selected`;
  }

  switch (action) {
    case NodeActions.ABORT:
      return `${nodeString} cannot abort action`;
    case NodeActions.ACQUIRE:
      return `${nodeString} cannot be allocated`;
    case NodeActions.CLONE:
      return `${nodeString} cannot be cloned to`;
    case NodeActions.COMMISSION:
      return `${nodeString} cannot be commissioned`;
    case NodeActions.DELETE:
      return `${nodeString} cannot be deleted`;
    case NodeActions.DEPLOY:
      return `${nodeString} cannot be deployed`;
    case NodeActions.EXIT_RESCUE_MODE:
      return `${nodeString} cannot exit rescue mode`;
    case NodeActions.IMPORT_IMAGES:
      return `${nodeString} cannot import images`;
    case NodeActions.LOCK:
      return `${nodeString} cannot be locked`;
    case NodeActions.MARK_BROKEN:
      return `${nodeString} cannot be marked broken`;
    case NodeActions.MARK_FIXED:
      return `${nodeString} cannot be marked fixed`;
    case NodeActions.OFF:
      return `${nodeString} cannot be powered off`;
    case NodeActions.ON:
      return `${nodeString} cannot be powered on`;
    case NodeActions.OVERRIDE_FAILED_TESTING:
      return `Cannot override failed tests on ${nodeString}`;
    case NodeActions.RELEASE:
      return `${nodeString} cannot be released`;
    case NodeActions.RESCUE_MODE:
      return `${nodeString} cannot be put in rescue mode`;
    case NodeActions.SET_POOL:
      return `Cannot set pool of ${nodeString}`;
    case NodeActions.SET_ZONE:
      return `Cannot set zone of ${nodeString}`;
    case NodeActions.TAG:
      return `${nodeString} cannot be tagged`;
    case NodeActions.TEST:
      return `${nodeString} cannot be tested`;
    case NodeActions.UNLOCK:
      return `${nodeString} cannot be unlocked`;
    default:
      return `${nodeString} cannot perform action`;
  }
};

type Props = {
  action: NodeActions;
  nodeType: string;
  selectedCount: number;
  actionableNodeIDs?: string[];
  onUpdateSelected?: () => void;
};

const NodeActionWarning = ({
  action,
  nodeType,
  selectedCount,
  onUpdateSelected,
}: Props): React.ReactElement => {
  return (
    <p data-testid="node-action-warning">
      <i className="p-icon--warning" />
      <span className="u-nudge-right--small">
        {getErrorSentence(action, nodeType, selectedCount)}. To proceed,{" "}
        {onUpdateSelected ? (
          <Button
            appearance="link"
            className="u-no-margin--bottom"
            data-testid="on-update-selected"
            onClick={onUpdateSelected}
          >
            update your selection
          </Button>
        ) : (
          "update your selection"
        )}
        .
      </span>
    </p>
  );
};

export default NodeActionWarning;
