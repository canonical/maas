import type { ReactNode } from "react";
import { useEffect } from "react";

import NodeActionWarning from "@/app/base/components/node/NodeActionWarning";
import { useCycled, useScrollOnRender } from "@/app/base/hooks";
import type { ClearSidePanelContent } from "@/app/base/types";
import type { Node, NodeActions } from "@/app/store/types/node";
import { canOpenActionForm } from "@/app/store/utils";

type Props = {
  action: NodeActions;
  children: ReactNode;
  clearSidePanelContent?: ClearSidePanelContent;
  nodes: Node[];
  nodeType: string;
  processingCount: number;
  onUpdateSelected: (nodeIDs: Node["system_id"][]) => void;
  viewingDetails: boolean;
};

export const NodeActionFormWrapper = ({
  action,
  children,
  clearSidePanelContent,
  nodes,
  nodeType,
  onUpdateSelected,
  processingCount,
  viewingDetails,
}: Props): React.ReactElement => {
  const onRenderRef = useScrollOnRender<HTMLDivElement>();
  const [actionStarted] = useCycled(processingCount !== 0);
  const actionableNodeIDs = nodes.reduce<Node["system_id"][]>(
    (nodeIDs, node) =>
      canOpenActionForm(node, action) ? [...nodeIDs, node.system_id] : nodeIDs,
    []
  );
  // Show a warning if not all the selected nodes can perform the selected
  // action, unless an action has already been started in which case we want to
  // maintain the form being rendered.
  const showWarning =
    !viewingDetails &&
    !actionStarted &&
    actionableNodeIDs.length !== nodes.length;

  useEffect(() => {
    if (nodes.length === 0) {
      // All the nodes were deselected so close the form.
      clearSidePanelContent?.();
    }
  }, [clearSidePanelContent, nodes.length]);

  return (
    <div ref={onRenderRef}>
      {showWarning ? (
        <NodeActionWarning
          action={action}
          nodeType={nodeType}
          onUpdateSelected={() => {
            onUpdateSelected(actionableNodeIDs);
          }}
          selectedCount={nodes.length - actionableNodeIDs.length}
        />
      ) : (
        children
      )}
    </div>
  );
};

export default NodeActionFormWrapper;
