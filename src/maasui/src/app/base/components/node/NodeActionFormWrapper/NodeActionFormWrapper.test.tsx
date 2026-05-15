import userEvent from "@testing-library/user-event";

import NodeActionFormWrapper from "./NodeActionFormWrapper";

import type { Node } from "@/app/store/types/node";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { mockFormikFormSaved } from "@/testing/mockFormikFormSaved";
import { render, screen, waitFor, renderWithProviders } from "@/testing/utils";

describe("NodeActionFormWrapper", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders children if all selected nodes can perform selected action", () => {
    const nodes = [
      factory.machine({ system_id: "abc123", actions: [NodeActions.ABORT] }),
      factory.machine({ system_id: "def456", actions: [NodeActions.ABORT] }),
    ];
    renderWithProviders(
      <NodeActionFormWrapper
        action={NodeActions.ABORT}
        clearSidePanelContent={vi.fn()}
        nodeType="node"
        nodes={nodes}
        onUpdateSelected={vi.fn()}
        processingCount={0}
        viewingDetails={false}
      >
        <span data-testid="children">Children</span>
      </NodeActionFormWrapper>
    );

    expect(screen.getByTestId("children")).toBeInTheDocument();
    expect(screen.queryByTestId("node-action-warning")).not.toBeInTheDocument();
  });

  it("displays a warning if not all selected nodes can perform selected action", () => {
    const nodes = [
      factory.machine({ system_id: "abc123", actions: [NodeActions.ABORT] }),
      factory.machine({ system_id: "def456", actions: [] }),
    ];
    renderWithProviders(
      <NodeActionFormWrapper
        action={NodeActions.ABORT}
        clearSidePanelContent={vi.fn()}
        nodeType="node"
        nodes={nodes}
        onUpdateSelected={vi.fn()}
        processingCount={0}
        viewingDetails={false}
      >
        <span data-testid="children">Children</span>
      </NodeActionFormWrapper>
    );

    expect(screen.getByTestId("node-action-warning")).toBeInTheDocument();
    expect(screen.queryByTestId("children")).not.toBeInTheDocument();
  });

  it(`does not display a warning when action has started even if not all
      selected nodes can perform selected action`, async () => {
    // Mock that action has started.
    mockFormikFormSaved();
    const nodes = [
      factory.machine({ system_id: "abc123", actions: [NodeActions.ABORT] }),
      factory.machine({ system_id: "def456", actions: [] }),
    ];
    renderWithProviders(
      <NodeActionFormWrapper
        action={NodeActions.ABORT}
        clearSidePanelContent={vi.fn()}
        nodeType="node"
        nodes={nodes}
        onUpdateSelected={vi.fn()}
        processingCount={0}
        viewingDetails={false}
      >
        <span data-testid="children">Children</span>
      </NodeActionFormWrapper>
    );

    expect(screen.getByTestId("children")).toBeInTheDocument();
    expect(screen.queryByTestId("node-action-warning")).not.toBeInTheDocument();
  });

  it("can run a function on actionable nodes if warning is shown", async () => {
    const onUpdateSelected = vi.fn();
    const nodes = [
      factory.machine({ system_id: "abc123", actions: [NodeActions.ABORT] }),
      factory.machine({ system_id: "def456", actions: [] }),
    ];
    renderWithProviders(
      <NodeActionFormWrapper
        action={NodeActions.ABORT}
        clearSidePanelContent={vi.fn()}
        nodeType="node"
        nodes={nodes}
        onUpdateSelected={onUpdateSelected}
        processingCount={0}
        viewingDetails={false}
      >
        Children
      </NodeActionFormWrapper>
    );

    await userEvent.click(screen.getByTestId("on-update-selected"));

    expect(onUpdateSelected).toHaveBeenCalledWith(["abc123"]);
  });

  it("clears header content if no nodes are provided", async () => {
    const clearSidePanelContent = vi.fn();
    const Proxy = ({ nodes }: { nodes: Node[] }) => (
      <NodeActionFormWrapper
        action={NodeActions.ABORT}
        clearSidePanelContent={clearSidePanelContent}
        nodeType="node"
        nodes={nodes}
        onUpdateSelected={vi.fn()}
        processingCount={0}
        viewingDetails={false}
      >
        Children
      </NodeActionFormWrapper>
    );
    // Render with one node selected.
    const { rerender } = render(<Proxy nodes={[factory.machine()]} />);

    expect(clearSidePanelContent).not.toHaveBeenCalled();

    // Update with no nodes selected - clear header content should be called.
    rerender(<Proxy nodes={[]} />);

    await waitFor(() => {
      expect(clearSidePanelContent).toHaveBeenCalled();
    });
  });
});
