import MachineSelectBox from "./MachineSelectBox";

import { machineActions } from "@/app/store/machine";
import * as query from "@/app/store/machine/utils/query";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  renderWithProviders,
  waitFor,
} from "@/testing/utils";

describe("MachineSelectBox", () => {
  beforeEach(() => {
    vi.spyOn(query, "generateCallId")
      .mockReturnValueOnce("mocked-nanoid-1")
      .mockReturnValueOnce("mocked-nanoid-2");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("displays a listbox and a search input field", async () => {
    renderWithProviders(<MachineSelectBox onSelect={vi.fn()} />);

    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("fetches machines on mount", async () => {
    const state = factory.rootState();

    const { store } = renderWithProviders(
      <MachineSelectBox onSelect={vi.fn()} />,
      {
        state,
      }
    );

    expect(screen.getByRole("listbox")).toBeInTheDocument();
    const expectedAction = machineActions.fetch("mocked-nanoid-1", {
      filter: { free_text: "" },
      group_collapsed: undefined,
      group_key: null,
      page_number: 1,
      page_size: 5,
      sort_direction: null,
      sort_key: null,
    });
    expect(
      store.getActions().find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });

  it("requests machines filtered by the free text input value", async () => {
    const state = factory.rootState();

    const { store } = renderWithProviders(
      <MachineSelectBox onSelect={vi.fn()} />,
      {
        state,
      }
    );

    await userEvent.type(screen.getByRole("combobox"), "test-machine");
    const expectedActionParams = {
      group_collapsed: undefined,
      group_key: null,
      page_number: 1,
      page_size: 5,
      sort_direction: null,
      sort_key: null,
    };
    const expectedInitialAction = machineActions.fetch("mocked-nanoid-1", {
      filter: { free_text: "" },
      ...expectedActionParams,
    });
    const expectedAction = machineActions.fetch("mocked-nanoid-2", {
      filter: { free_text: "test-machine" },
      ...expectedActionParams,
    });

    await waitFor(() => {
      expect(
        store
          .getActions()
          .filter((action) => action.type === expectedAction.type).length
      ).toEqual(2);
    });
    const machineFetchActions = store
      .getActions()
      .filter((action) => action.type === expectedAction.type);
    expect(machineFetchActions[0]).toStrictEqual(expectedInitialAction);
    expect(machineFetchActions[1]).toStrictEqual(expectedAction);
  });
});
