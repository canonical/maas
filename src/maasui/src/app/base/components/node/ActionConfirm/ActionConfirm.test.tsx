import * as reactComponentHooks from "@canonical/react-components/dist/hooks";

import ActionConfirm from "./ActionConfirm";

import * as maasUiHooks from "@/app/base/hooks/analytics";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

vi.mock("@canonical/react-components/dist/hooks", () => ({
  usePrevious: vi.fn(),
}));

describe("ActionConfirm", () => {
  it("can show saving state", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ system_id: "abc123" })],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus({ deletingFilesystem: true }),
        }),
      }),
    });

    renderWithProviders(
      <ActionConfirm
        closeExpanded={vi.fn()}
        confirmLabel="Confirm"
        eventName="deleteFilesystem"
        message={<span>Are you sure you want to do that?</span>}
        onConfirm={vi.fn()}
        onSaveAnalytics={{
          action: "Action",
          category: "Category",
          label: "Label",
        }}
        statusKey="deletingFilesystem"
        systemId="abc123"
      />,
      { state }
    );

    const actionButton = screen.getByRole("button", {
      name: "Waiting for action to complete",
    });
    expect(actionButton).toBeInTheDocument();
    expect(actionButton).toHaveClass("is-processing");
  });

  it("can show errors", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        eventErrors: [
          factory.machineEventError({
            id: "abc123",
            event: "deleteFilesystem",
            error: "uh oh",
          }),
        ],
        items: [factory.machineDetails({ system_id: "abc123" })],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus({ deletingFilesystem: false }),
        }),
      }),
    });

    const closeExpanded = vi.fn();
    renderWithProviders(
      <ActionConfirm
        closeExpanded={closeExpanded}
        confirmLabel="Confirm"
        message="Are you sure you want to do that?"
        onConfirm={vi.fn()}
        onSaveAnalytics={{
          action: "Action",
          category: "Category",
          label: "Label",
        }}
        statusKey="deletingFilesystem"
        systemId="abc123"
      />,
      { state }
    );

    expect(screen.getByTestId("error-message")).toHaveTextContent("uh oh");
  });

  it("can change the submit appearance", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ system_id: "abc123" })],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus({ creatingCacheSet: false }),
        }),
      }),
    });

    const closeExpanded = vi.fn();
    renderWithProviders(
      <ActionConfirm
        closeExpanded={closeExpanded}
        confirmLabel="Confirm"
        message="Are you sure you want to do that?"
        onConfirm={vi.fn()}
        onSaveAnalytics={{
          action: "Action",
          category: "Category",
          label: "Label",
        }}
        statusKey="creatingCacheSet"
        submitAppearance="positive"
        systemId="abc123"
      />,
      { state }
    );

    expect(screen.getByRole("button", { name: "Confirm" })).toHaveClass(
      "p-button--positive"
    );
  });

  it("sends an analytics event when saved", () => {
    const analyticsEvent = {
      action: "Action",
      category: "Category",
      label: "Label",
    };
    const useSendMock = vi.spyOn(maasUiHooks, "useSendAnalyticsWhen");
    // Mock saved state by simulating "deletingFilesystem" changing from true to false
    vi.spyOn(reactComponentHooks, "usePrevious").mockImplementation(() => true);
    const state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ system_id: "abc123" })],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus({ deletingFilesystem: false }),
        }),
      }),
    });

    const closeExpanded = vi.fn();
    renderWithProviders(
      <ActionConfirm
        closeExpanded={closeExpanded}
        confirmLabel="Confirm"
        eventName="deleteFilesystem"
        message="Are you sure you want to do that?"
        onConfirm={vi.fn()}
        onSaveAnalytics={analyticsEvent}
        statusKey="deletingFilesystem"
        systemId="abc123"
      />,
      { state }
    );

    expect(useSendMock).toHaveBeenCalled();
    expect(useSendMock.mock.calls[0]).toEqual([
      true,
      analyticsEvent.category,
      analyticsEvent.action,
      analyticsEvent.label,
    ]);
    useSendMock.mockRestore();
  });

  it("closes the form when saved", () => {
    // Mock saved state by simulating "deletingFilesystem" changing from true to false
    vi.spyOn(reactComponentHooks, "usePrevious").mockImplementation(() => true);
    const state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ system_id: "abc123" })],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus({ deletingFilesystem: false }),
        }),
      }),
    });

    const closeExpanded = vi.fn();
    renderWithProviders(
      <ActionConfirm
        closeExpanded={closeExpanded}
        confirmLabel="Confirm"
        eventName="deleteFilesystem"
        message="Are you sure you want to do that?"
        onConfirm={vi.fn()}
        onSaveAnalytics={{
          action: "Action",
          category: "Category",
          label: "Label",
        }}
        statusKey="deletingFilesystem"
        systemId="abc123"
      />,
      { state }
    );

    expect(closeExpanded).toHaveBeenCalled();
  });
});
