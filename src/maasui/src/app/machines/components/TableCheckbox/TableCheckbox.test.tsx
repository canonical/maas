import TableCheckbox, { Checked } from "./TableCheckbox";

import { machineActions } from "@/app/store/machine";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

let state: RootState;
const callId = "123456";

beforeEach(() => {
  state = factory.rootState({
    machine: factory.machineState({
      lists: {
        [callId]: factory.machineStateList({
          count: 10,
        }),
      },
    }),
  });
});

it("can be unchecked", () => {
  renderWithProviders(
    <TableCheckbox
      callId={callId}
      isChecked={Checked.Unchecked}
      onGenerateSelected={vi.fn()}
    />,
    { state }
  );
  expect(screen.getByRole("checkbox")).not.toBeChecked();
});

it("can be checked", () => {
  renderWithProviders(
    <TableCheckbox
      callId={callId}
      isChecked={Checked.Checked}
      onGenerateSelected={vi.fn()}
    />,
    { state }
  );
  expect(screen.getByRole("checkbox")).toBeChecked();
});

it("can be partially checked", () => {
  renderWithProviders(
    <TableCheckbox
      callId={callId}
      isChecked={Checked.Mixed}
      onGenerateSelected={vi.fn()}
    />,
    { state }
  );
  expect(screen.getByRole("checkbox")).toBePartiallyChecked();
});

it("can show a label", () => {
  renderWithProviders(
    <TableCheckbox
      callId={callId}
      inputLabel="Check all"
      isChecked={Checked.Checked}
      onGenerateSelected={vi.fn()}
    />,
    { state }
  );
  expect(
    screen.getByRole("checkbox", { name: "Check all" })
  ).toBeInTheDocument();
});

it("is disabled if there are no machines", () => {
  state.machine.lists[callId].count = 0;
  renderWithProviders(
    <TableCheckbox
      callId={callId}
      isChecked={Checked.Checked}
      onGenerateSelected={vi.fn()}
    />,
    { state }
  );
  expect(screen.getByRole("checkbox")).toBeDisabled();
});

it("is not disabled if there are machines", () => {
  state.machine.lists[callId].count = 20;
  renderWithProviders(
    <TableCheckbox
      callId={callId}
      isChecked={Checked.Checked}
      onGenerateSelected={vi.fn()}
    />,
    { state }
  );
  expect(screen.getByRole("checkbox")).not.toBeDisabled();
});

it("can be manually disabled", () => {
  renderWithProviders(
    <TableCheckbox
      callId={callId}
      isChecked={Checked.Checked}
      isDisabled
      onGenerateSelected={vi.fn()}
    />,
    { state }
  );
  expect(screen.getByRole("checkbox")).toBeDisabled();
});

it("can add additional classes to the wrapping element", () => {
  renderWithProviders(
    <TableCheckbox
      callId={callId}
      extraClasses="extra-class"
      isChecked={Checked.Checked}
      onGenerateSelected={vi.fn()}
    />,
    { state }
  );

  expect(document.querySelector(".p-form__group")).toHaveClass("extra-class");
});

it("can dispatch a generated selected state", async () => {
  const selected = { items: ["abc123", "def456"] };
  const { store } = renderWithProviders(
    <TableCheckbox
      callId={callId}
      extraClasses="extra-class"
      isChecked={Checked.Checked}
      onGenerateSelected={() => selected}
    />,
    { state }
  );
  await userEvent.click(screen.getByRole("checkbox"));
  const expected = machineActions.setSelected(selected);
  await waitFor(() => {
    expect(
      store.getActions().find((action) => action.type === expected.type)
    ).toStrictEqual(expected);
  });
});
