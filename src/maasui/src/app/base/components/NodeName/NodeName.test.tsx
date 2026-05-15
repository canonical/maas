import NodeName from "./NodeName";
import type { Props as NodeNameProps } from "./NodeName";

import type { Machine } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

describe("NodeName", () => {
  let state: RootState;
  let machine: Machine;

  beforeEach(() => {
    const domain = factory.domain({ id: 99 });
    machine = factory.machineDetails({
      domain,
      locked: false,
      permissions: ["edit"],
      system_id: "abc123",
    });
    state = factory.rootState({
      domain: factory.domainState({
        items: [domain],
      }),
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          data: [factory.powerType()],
        }),
      }),
      machine: factory.machineState({
        loaded: true,
        items: [machine],
      }),
    });
  });

  it("displays a spinner when loading", () => {
    state.machine.items = [];
    renderWithProviders(
      <NodeName
        editingName={false}
        node={null}
        onSubmit={vi.fn()}
        setEditingName={vi.fn()}
      />,
      { state }
    );

    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("displays just the name when not editable", () => {
    state.machine.items[0].locked = true;
    renderWithProviders(
      <NodeName
        editingName={false}
        node={machine}
        onSubmit={vi.fn()}
        setEditingName={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByText(state.machine.items[0].fqdn)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("displays name in a button", () => {
    renderWithProviders(
      <NodeName
        editingName={false}
        node={machine}
        onSubmit={vi.fn()}
        setEditingName={vi.fn()}
      />,
      { state }
    );

    expect(
      screen.getByRole("button", { name: state.machine.items[0].fqdn })
    ).toBeInTheDocument();
  });

  it("changes the form state when clicking the name", async () => {
    const setEditingName = vi.fn();
    renderWithProviders(
      <NodeName
        editingName={false}
        node={machine}
        onSubmit={vi.fn()}
        setEditingName={setEditingName}
      />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("button", { name: state.machine.items[0].fqdn })
    );
    expect(setEditingName).toHaveBeenCalled();
  });

  it("can display the form", () => {
    renderWithProviders(
      <NodeName
        editingName={true}
        node={machine}
        onSubmit={vi.fn()}
        setEditingName={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByRole("textbox", { name: "Hostname" })).toHaveValue(
      state.machine.items[0].hostname
    );
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("closes the form when it saves", async () => {
    state.machine.saving = false;
    const setEditingName = vi.fn();
    const ProxyNodeName = (props: NodeNameProps) => <NodeName {...props} />;
    const { rerender } = renderWithProviders(
      <ProxyNodeName
        editingName={true}
        node={machine}
        onSubmit={vi.fn()}
        saved={false}
        saving={false}
        setEditingName={setEditingName}
      />,
      { state }
    );

    rerender(
      <ProxyNodeName
        editingName={true}
        node={machine}
        onSubmit={vi.fn()}
        saved={false}
        saving={true}
        setEditingName={setEditingName}
      />
    );

    rerender(
      <ProxyNodeName
        editingName={true}
        node={machine}
        onSubmit={vi.fn()}
        saved={true}
        saving={false}
        setEditingName={setEditingName}
      />
    );

    await waitFor(() => {
      expect(setEditingName).toHaveBeenCalledWith(false);
    });
  });

  it("can display a hostname error", async () => {
    renderWithProviders(
      <NodeName
        editingName={true}
        node={machine}
        onSubmit={vi.fn()}
        setEditingName={vi.fn()}
      />,
      { state }
    );

    await userEvent.clear(screen.getByRole("textbox", { name: "Hostname" }));
    await userEvent.tab();
    expect(
      screen.getByText("hostname is a required field")
    ).toBeInTheDocument();
  });
});
